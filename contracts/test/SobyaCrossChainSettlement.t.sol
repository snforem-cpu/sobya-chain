// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaCrossChainSettlement.sol";
import "../src/SobyaSolverInventoryVault.sol";

interface VmSettlement {
    function deal(address account, uint256 newBalance) external;
    function warp(uint256 timestamp) external;
}

contract SobyaCrossChainSettlementTest {
    VmSettlement private constant vm = VmSettlement(address(uint160(uint256(keccak256("hevm cheat code")))));
    SobyaCrossChainSettlement private settlement;
    SobyaSolverInventoryVault private vault;

    function setUp() public {
        vault = new SobyaSolverInventoryVault();
        settlement = new SobyaCrossChainSettlement(ISobyaSolverInventoryVault(address(vault)));
        vm.deal(address(this), 10 ether);
        vault.deposit{value: 5 ether}();
    }

    function _reserve(bytes32 orderId, address payable recipient, uint128 amount) private {
        vault.reserve(orderId, recipient, amount, uint64(block.timestamp + 1 days));
    }

    function testExecutesReservedNativeSobyPayoutAndRecordsSourceBinding() public {
        bytes32 orderId = keccak256("settlement-order-1");
        bytes32 sourceChain = keccak256("TRON_MAINNET");
        bytes32 sourceEscrow = bytes32(uint256(uint160(address(0x1234))));
        bytes32 sourceAsset = bytes32(uint256(uint160(address(0x5678))));
        address payable recipient = payable(address(0xBEEF));
        uint256 beforeBalance = recipient.balance;
        _reserve(orderId, recipient, uint128(1 ether));

        settlement.executePayout(orderId, sourceChain, sourceEscrow, sourceAsset, 25_000_000);

        require(recipient.balance == beforeBalance + 1 ether, "recipient not paid");
        require(settlement.orderStatus(orderId) == SobyaCrossChainSettlement.Status.PAID, "not marked paid");
        (
            bytes32 storedChain,
            bytes32 storedEscrow,
            bytes32 storedAsset,
            uint256 sourceAmount,
            address storedRecipient,
            uint256 sobyAmount,
            address solver,
            uint256 destinationChainId
        ) = settlement.payouts(orderId);
        require(storedChain == sourceChain && storedEscrow == sourceEscrow, "source mismatch");
        require(storedAsset == sourceAsset && sourceAmount == 25_000_000, "asset mismatch");
        require(storedRecipient == recipient && sobyAmount == 1 ether, "payout mismatch");
        require(solver == address(this), "solver mismatch");
        require(destinationChainId == block.chainid, "destination chain mismatch");
        require(vault.reserved(address(this)) == 0, "reservation not consumed");
    }

    function testOrderCannotBePaidTwice() public {
        bytes32 orderId = keccak256("settlement-order-duplicate");
        _reserve(orderId, payable(address(0xBEEF)), uint128(1 ether));
        settlement.executePayout(orderId, keccak256("ETHEREUM_MAINNET"),
            bytes32(uint256(uint160(address(0x1234)))),
            bytes32(uint256(uint160(address(0x5678)))), 10_000_000);
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, keccak256("ETHEREUM_MAINNET"),
            bytes32(uint256(uint160(address(0x1234)))),
            bytes32(uint256(uint160(address(0x5678)))), 10_000_000
        ));
        require(!ok, "duplicate payout accepted");
    }

    function testRejectsInvalidSourceBinding() public {
        bytes32 orderId = keccak256("bad-order");
        _reserve(orderId, payable(address(0xBEEF)), uint128(1 ether));
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, bytes32(0),
            bytes32(uint256(1)), bytes32(uint256(2)), 1
        ));
        require(!ok, "zero source chain accepted");
    }

    function testCannotPayAfterReservationExpiry() public {
        bytes32 orderId = keccak256("expired-order");
        uint64 deadline = uint64(block.timestamp + 1 hours);
        vault.reserve(orderId, payable(address(0xBEEF)), uint128(1 ether), deadline);
        vm.warp(deadline);
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, keccak256("SOLANA_MAINNET"),
            bytes32(uint256(1)), bytes32(uint256(2)), 1
        ));
        require(!ok, "expired reservation paid");
    }
}
