// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SOBYA Proof Registry
/// @notice Records SHA-256 document fingerprints against an exact 1 SOBY service payment.
contract SobyaProofRegistry {
    uint256 public constant PROOF_FEE = 1 ether;
    address public immutable feeRecipient;
    mapping(bytes32 => bool) public isRecorded;
    uint256 private unlocked = 1;

    event ProofRecorded(
        address indexed submitter,
        bytes32 indexed documentHash,
        uint256 fee,
        uint256 timestamp
    );

    constructor(address feeRecipient_) {
        require(feeRecipient_ != address(0), "SOBYA_PROOF: ZERO_RECIPIENT");
        feeRecipient = feeRecipient_;
    }

    modifier nonReentrant() {
        require(unlocked == 1, "SOBYA_PROOF: REENTRANT");
        unlocked = 0;
        _;
        unlocked = 1;
    }

    /// @notice Record a SHA-256 fingerprint and pay the fixed service fee atomically.
    function recordProof(bytes32 documentHash) external payable nonReentrant {
        require(documentHash != bytes32(0), "SOBYA_PROOF: EMPTY_HASH");
        require(msg.value == PROOF_FEE, "SOBYA_PROOF: INCORRECT_FEE");
        require(!isRecorded[documentHash], "SOBYA_PROOF: ALREADY_RECORDED");

        isRecorded[documentHash] = true;
        (bool sent,) = payable(feeRecipient).call{value: msg.value}("");
        require(sent, "SOBYA_PROOF: FEE_TRANSFER_FAILED");

        emit ProofRecorded(msg.sender, documentHash, msg.value, block.timestamp);
    }
}
