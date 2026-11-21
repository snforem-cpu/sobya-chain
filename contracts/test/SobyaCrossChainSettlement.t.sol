// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaCrossChainSettlement.sol";
import "../src/SobyaSolverInventoryVault.sol";

interface VmSettlement {
    function deal(address account, uint256 newBalance) external;
    function warp(uint256 timestamp) external;
    function addr(uint256 privateKey) external returns (address);
    function sign(uint256 privateKey, bytes32 digest)
        external returns (uint8 v, bytes32 r, bytes32 s);
}

contract SobyaCrossChainSettlementTest {
    VmSettlement private constant vm = VmSettlement(address(uint160(uint256(keccak256("hevm cheat code")))));
    uint256 private constant KEY_A = 0xA11CE;
    uint256 private constant KEY_B = 0xB0B;
    uint256 private constant KEY_C = 0xCAFE;
    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 private constant PAYOUT_TYPEHASH = keccak256(
        "SourceDepositAttestation(bytes32 orderId,bytes32 sourceChain,bytes32 sourceEscrow,bytes32 sourceAsset,uint256 sourceAmount,address recipient,uint256 sobyAmount,address solver,uint256 destinationChainId,uint64 releaseAfter)"
    );

    SobyaCrossChainSettlement private settlement;
    SobyaSolverInventoryVault private vault;

    function setUp() public {
        vault = new SobyaSolverInventoryVault();
        address[] memory attestors = new address[](3);
        attestors[0] = vm.addr(KEY_A);
        attestors[1] = vm.addr(KEY_B);
        attestors[2] = vm.addr(KEY_C);
        settlement = new SobyaCrossChainSettlement(
            ISobyaSolverInventoryVault(address(vault)), attestors, 2
        );
        vm.deal(address(this), 10 ether);
        vault.deposit{value: 5 ether}();
    }

    function _reserve(bytes32 orderId, address payable recipient, uint128 amount)
        private returns (uint64 releaseAfter)
    {
        releaseAfter = uint64(block.timestamp + 1 days);
        vault.reserve(orderId, recipient, amount, releaseAfter);
    }

    function _signatures(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount
    ) private returns (bytes[] memory signatures) {
        (address solver, address recipient, uint128 amount, uint64 releaseAfter, bool active) =
            vault.reservations(orderId);
        require(active, "reservation missing");
        bytes32 domainSeparator = keccak256(abi.encode(
            DOMAIN_TYPEHASH,
            keccak256("SOBYA Cross-Chain Settlement"),
            keccak256("1"),
            block.chainid,
            address(settlement)
        ));
        bytes32 structHash = keccak256(abi.encode(
            PAYOUT_TYPEHASH, orderId, sourceChain, sourceEscrow, sourceAsset,
            sourceAmount, recipient, uint256(amount), solver, block.chainid, releaseAfter
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, structHash));

        uint256[2] memory keys = [KEY_A, KEY_B];
        if (uint160(vm.addr(keys[0])) > uint160(vm.addr(keys[1]))) {
            (keys[0], keys[1]) = (keys[1], keys[0]);
        }
        signatures = new bytes[](2);
        for (uint256 i; i < 2; ++i) {
            (uint8 v, bytes32 r, bytes32 s) = vm.sign(keys[i], digest);
            signatures[i] = abi.encodePacked(r, s, v);
        }
    }

    function _execute(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount
    ) private {
        settlement.executePayout(
            orderId, sourceChain, sourceEscrow, sourceAsset, sourceAmount,
            _signatures(orderId, sourceChain, sourceEscrow, sourceAsset, sourceAmount)
        );
    }

    function testExecutesReservedNativeSobyPayoutOnlyAfterThresholdSourceAttestation() public {
        bytes32 orderId = keccak256("settlement-order-1");
        bytes32 sourceChain = keccak256("TRON_MAINNET");
        bytes32 sourceEscrow = bytes32(uint256(uint160(address(0x1234))));
        bytes32 sourceAsset = bytes32(uint256(uint160(address(0x5678))));
        address payable recipient = payable(address(0xBEEF));
        uint256 beforeBalance = recipient.balance;
        _reserve(orderId, recipient, uint128(1 ether));

        _execute(orderId, sourceChain, sourceEscrow, sourceAsset, 25_000_000);

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

    function testRejectsPayoutWithoutSourceDepositAttestations() public {
        bytes32 orderId = keccak256("unattested-order");
        _reserve(orderId, payable(address(0xBEEF)), uint128(1 ether));
        bytes[] memory noSignatures = new bytes[](0);
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, keccak256("ETHEREUM_MAINNET"),
            bytes32(uint256(0x1234)), bytes32(uint256(0x5678)), 10_000_000, noSignatures
        ));
        require(!ok, "unattested payout accepted");
        require(vault.reserved(address(this)) == 1 ether, "reservation unexpectedly consumed");
    }

    function testOrderCannotBePaidTwice() public {
        bytes32 orderId = keccak256("settlement-order-duplicate");
        _reserve(orderId, payable(address(0xBEEF)), uint128(1 ether));
        bytes32 chain = keccak256("ETHEREUM_MAINNET");
        bytes32 escrow = bytes32(uint256(uint160(address(0x1234))));
        bytes32 asset = bytes32(uint256(uint160(address(0x5678))));
        _execute(orderId, chain, escrow, asset, 10_000_000);
        bytes[] memory signatures = _signatures(orderId, chain, escrow, asset, 10_000_000);
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, chain, escrow, asset, 10_000_000, signatures
        ));
        require(!ok, "duplicate payout accepted");
    }

    function testRejectsInvalidSourceBinding() public {
        bytes32 orderId = keccak256("bad-order");
        _reserve(orderId, payable(address(0xBEEF)), uint128(1 ether));
        bytes[] memory signatures = _signatures(
            orderId, bytes32(0), bytes32(uint256(1)), bytes32(uint256(2)), 1
        );
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, bytes32(0),
            bytes32(uint256(1)), bytes32(uint256(2)), 1, signatures
        ));
        require(!ok, "zero source chain accepted");
    }

    function testCannotPayAfterReservationExpiry() public {
        bytes32 orderId = keccak256("expired-order");
        uint64 deadline = uint64(block.timestamp + 1 hours);
        vault.reserve(orderId, payable(address(0xBEEF)), uint128(1 ether), deadline);
        vm.warp(deadline);
        bytes[] memory signatures = _signatures(
            orderId, keccak256("SOLANA_MAINNET"), bytes32(uint256(1)), bytes32(uint256(2)), 1
        );
        (bool ok,) = address(settlement).call(abi.encodeWithSelector(
            settlement.executePayout.selector, orderId, keccak256("SOLANA_MAINNET"),
            bytes32(uint256(1)), bytes32(uint256(2)), 1, signatures
        ));
        require(!ok, "expired reservation paid");
    }
}
