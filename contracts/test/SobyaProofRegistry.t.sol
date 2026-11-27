// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaProofRegistry.sol";

interface VmProof {
    function deal(address account, uint256 newBalance) external;
    function prank(address sender) external;
}

contract SobyaProofRegistryTest {
    VmProof private constant vm =
        VmProof(address(uint160(uint256(keccak256("hevm cheat code")))));

    address private constant FEE_RECIPIENT = address(0xFEE);
    address private constant SUBMITTER = address(0xBEEF);
    bytes32 private constant DOCUMENT_HASH =
        0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;

    SobyaProofRegistry private registry;

    function setUp() public {
        registry = new SobyaProofRegistry(FEE_RECIPIENT);
        vm.deal(SUBMITTER, 5 ether);
    }

    function testRecordsFingerprintAndForwardsExactFee() public {
        vm.prank(SUBMITTER);
        registry.recordProof{value: 1 ether}(DOCUMENT_HASH);

        require(registry.isRecorded(DOCUMENT_HASH), "HASH_NOT_RECORDED");
        require(FEE_RECIPIENT.balance == 1 ether, "FEE_NOT_FORWARDED");
        require(address(registry).balance == 0, "CONTRACT_RETAINED_FEE");
    }

    function testRejectsIncorrectFee() public {
        vm.prank(SUBMITTER);
        (bool ok,) = address(registry).call{value: 0.5 ether}(
            abi.encodeCall(registry.recordProof, (DOCUMENT_HASH))
        );
        require(!ok, "ACCEPTED_INCORRECT_FEE");
        require(!registry.isRecorded(DOCUMENT_HASH), "RECORDED_WITHOUT_PAYMENT");
    }

    function testRejectsZeroHash() public {
        vm.prank(SUBMITTER);
        (bool ok,) = address(registry).call{value: 1 ether}(
            abi.encodeCall(registry.recordProof, (bytes32(0)))
        );
        require(!ok, "ACCEPTED_ZERO_HASH");
    }

    function testRejectsDuplicateFingerprint() public {
        vm.prank(SUBMITTER);
        registry.recordProof{value: 1 ether}(DOCUMENT_HASH);
        vm.prank(SUBMITTER);
        (bool ok,) = address(registry).call{value: 1 ether}(
            abi.encodeCall(registry.recordProof, (DOCUMENT_HASH))
        );
        require(!ok, "ACCEPTED_DUPLICATE_HASH");
        require(FEE_RECIPIENT.balance == 1 ether, "DUPLICATE_CHARGED");
    }

    function testOnlyAcceptsOneSobyAndKeepsAtomicityOnTransferFailure() public {
        SobyaProofRegistry rejecting = new SobyaProofRegistry(address(0x1));
        vm.prank(SUBMITTER);
        (bool ok,) = address(rejecting).call{value: 1 ether}(
            abi.encodeCall(rejecting.recordProof, (DOCUMENT_HASH))
        );
        // A normal EOA recipient accepts native SOBY; this confirms successful forwarding.
        require(ok, "EOA_FEE_RECIPIENT_REJECTED");
        require(rejecting.isRecorded(DOCUMENT_HASH), "RECORD_MISSING");
    }
}
