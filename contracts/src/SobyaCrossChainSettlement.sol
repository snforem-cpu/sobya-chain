// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaSolverInventoryVault {
    function reservations(bytes32 orderId) external view returns (
        address solver, address recipient, uint128 amount, uint64 releaseAfter, bool active
    );
    function executePayout(bytes32 orderId) external;
}

/// @title SOBYA Cross-Chain Settlement
/// @notice Pays only a reserved amount after a strict-majority source-deposit attestation.
/// @dev Attestors must independently verify the exact finalized source-chain escrow deposit.
///      The attestor set is an explicit trust boundary, not a trustless light client.
contract SobyaCrossChainSettlement {
    enum Status { NONE, PAID }

    struct Payout {
        bytes32 sourceChain;
        bytes32 sourceEscrow;
        bytes32 sourceAsset;
        uint256 sourceAmount;
        address recipient;
        uint256 sobyAmount;
        address solver;
        uint256 destinationChainId;
    }

    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 private constant PAYOUT_TYPEHASH = keccak256(
        "SourceDepositAttestation(bytes32 orderId,bytes32 sourceChain,bytes32 sourceEscrow,bytes32 sourceAsset,uint256 sourceAmount,address recipient,uint256 sobyAmount,address solver,uint256 destinationChainId,uint64 releaseAfter)"
    );
    bytes32 private constant NAME_HASH = keccak256("SOBYA Cross-Chain Settlement");
    bytes32 private constant VERSION_HASH = keccak256("1");
    uint256 private constant SECP256K1_HALF_ORDER =
        0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    ISobyaSolverInventoryVault public immutable inventoryVault;
    uint8 public immutable attestationThreshold;
    uint8 public immutable attestorCount;
    mapping(address => bool) public isAttestor;
    mapping(bytes32 => Status) public orderStatus;
    mapping(bytes32 => Payout) public payouts;
    uint256 private entered = 1;

    event PayoutExecuted(
        bytes32 indexed orderId,
        bytes32 indexed sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount,
        address indexed recipient,
        uint256 sobyAmount,
        address solver,
        uint256 destinationChainId
    );

    error InvalidPayout();
    error OrderAlreadyPaid();
    error ReentrantCall();
    error ReservationUnavailable();
    error InvalidAttestorSet();
    error InvalidAttestation();

    modifier nonReentrant() {
        if (entered != 1) revert ReentrantCall();
        entered = 2;
        _;
        entered = 1;
    }

    constructor(
        ISobyaSolverInventoryVault vault,
        address[] memory attestors,
        uint8 threshold
    ) {
        if (address(vault) == address(0)) revert InvalidPayout();
        if (
            attestors.length < 3 || attestors.length > type(uint8).max ||
            threshold <= attestors.length / 2 || threshold > attestors.length
        ) revert InvalidAttestorSet();
        for (uint256 i; i < attestors.length; ++i) {
            address attestor = attestors[i];
            if (attestor == address(0) || isAttestor[attestor]) revert InvalidAttestorSet();
            isAttestor[attestor] = true;
        }
        inventoryVault = vault;
        attestationThreshold = threshold;
        attestorCount = uint8(attestors.length);
    }

    /// @notice Pays the fixed vault recipient only after a threshold signs the exact source deposit.
    /// @dev Signatures are EIP-712 scoped to this SOBYA chain and this settlement contract.
    ///      Signers must be supplied in strictly increasing recovered-address order.
    function executePayout(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount,
        bytes[] calldata sourceAttestations
    ) external nonReentrant {
        if (
            orderId == bytes32(0) || sourceChain == bytes32(0) ||
            sourceEscrow == bytes32(0) || sourceAsset == bytes32(0) ||
            sourceAmount == 0
        ) revert InvalidPayout();
        if (orderStatus[orderId] != Status.NONE) revert OrderAlreadyPaid();

        (address solver, address recipient, uint128 amount, uint64 releaseAfter, bool active) =
            inventoryVault.reservations(orderId);
        if (
            !active || solver == address(0) || recipient == address(0) ||
            amount == 0 || block.timestamp >= releaseAfter
        ) revert ReservationUnavailable();

        _verifySourceAttestations(
            orderId, sourceChain, sourceEscrow, sourceAsset, sourceAmount,
            recipient, amount, solver, releaseAfter, sourceAttestations
        );

        orderStatus[orderId] = Status.PAID;
        payouts[orderId] = Payout({
            sourceChain: sourceChain,
            sourceEscrow: sourceEscrow,
            sourceAsset: sourceAsset,
            sourceAmount: sourceAmount,
            recipient: recipient,
            sobyAmount: amount,
            solver: solver,
            destinationChainId: block.chainid
        });

        inventoryVault.executePayout(orderId);

        emit PayoutExecuted(
            orderId, sourceChain, sourceEscrow, sourceAsset, sourceAmount,
            recipient, amount, solver, block.chainid
        );
    }

    function _verifySourceAttestations(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount,
        address recipient,
        uint128 amount,
        address solver,
        uint64 releaseAfter,
        bytes[] calldata signatures
    ) private view {
        if (
            signatures.length < attestationThreshold ||
            signatures.length > attestorCount
        ) revert InvalidAttestation();

        bytes32 domainSeparator = keccak256(abi.encode(
            DOMAIN_TYPEHASH, NAME_HASH, VERSION_HASH, block.chainid, address(this)
        ));
        bytes32 structHash = keccak256(abi.encode(
            PAYOUT_TYPEHASH, orderId, sourceChain, sourceEscrow, sourceAsset,
            sourceAmount, recipient, uint256(amount), solver, block.chainid, releaseAfter
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, structHash));

        address previousSigner;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(digest, signatures[i]);
            if (
                signer == address(0) || !isAttestor[signer] ||
                uint160(signer) <= uint160(previousSigner)
            ) revert InvalidAttestation();
            previousSigner = signer;
        }
    }

    function _recover(bytes32 digest, bytes calldata signature) private pure returns (address signer) {
        if (signature.length != 65) revert InvalidAttestation();
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (uint256(s) > SECP256K1_HALF_ORDER || (v != 27 && v != 28)) {
            revert InvalidAttestation();
        }
        signer = ecrecover(digest, v, r, s);
    }
}
