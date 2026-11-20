// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaCrossChainSettlement.sol";

interface VmSettlement {
    function deal(address account, uint256 newBalance) external;
}

contract RejectNativeRecipient {
    receive() external payable { revert("reject"); }
}

contract SobyaCrossChainSettlementTest {
    VmSettlement private constant vm = VmSettlement(address(uint160(uint256(keccak256("hevm cheat code")))));
    SobyaCrossChainSettlement private settlement;

    function setUp() public {
        settlement = new SobyaCrossChainSettlement();
        vm.deal(address(this), 10 ether);
    }

    function testExecutesNativeSobyPayoutAndRecordsSourceBinding() public {
        bytes32 orderId = keccak256("settlement-order-1");
        bytes32 sourceChain = keccak256("TRON_MAINNET");
        bytes32 sourceEscrow = bytes32(uint256(uint160(address(0x1234))));
        bytes32 sourceAsset = bytes32(uint256(uint160(address(0x5678))));
        address payable recipient = payable(address(0xBEEF));
        uint256 beforeBalance = recipient.balance;

        settlement.executePayout{value: 1 ether}(
            orderId, sourceChain, sourceEscrow, sourceAsset, 25_000_000, recipient
        );

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
    }

    function testOrderCannotBePaidTwice() public {
        bytes32 orderId = keccak256("settlement-order-duplicate");
        bytes32 sourceChain = keccak256("ETHEREUM_MAINNET");
        bytes32 sourceEscrow = bytes32(uint256(uint160(address(0x1234))));
        bytes32 sourceAsset = bytes32(uint256(uint160(address(0x5678))));
        address payable recipient = payable(address(0xBEEF));
        settlement.executePayout{value: 1 ether}(
            orderId, sourceChain, sourceEscrow, sourceAsset, 10_000_000, recipient
        );
        (bool ok,) = address(settlement).call{value: 1 ether}(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, sourceChain, sourceEscrow,
            sourceAsset, 10_000_000, recipient
        ));
        require(!ok, "duplicate payout accepted");
    }

    function testRejectsInvalidSourceBinding() public {
        (bool ok,) = address(settlement).call{value: 1 ether}(abi.encodeWithSelector(
            settlement.executePayout.selector, keccak256("bad-order"), bytes32(0),
            bytes32(uint256(1)), bytes32(uint256(2)), 1, payable(address(0xBEEF))
        ));
        require(!ok, "zero source chain accepted");
    }

    function testFailedRecipientTransferRevertsOrderState() public {
        bytes32 orderId = keccak256("settlement-rejecting-recipient");
        RejectNativeRecipient recipient = new RejectNativeRecipient();
        (bool ok,) = address(settlement).call{value: 1 ether}(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, keccak256("SOLANA_MAINNET"),
            bytes32(uint256(1)), bytes32(uint256(2)), 1, payable(address(recipient))
        ));
        require(!ok, "rejecting recipient unexpectedly paid");
        require(settlement.orderStatus(orderId) == SobyaCrossChainSettlement.Status.NONE, "state not reverted");
    }
}
