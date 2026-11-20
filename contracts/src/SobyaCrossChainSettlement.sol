// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SOBYA Cross-Chain Settlement
/// @notice Pays native SOBY to a destination wallet and emits an order-bound
///         event that independent source-chain attestors can verify.
/// @dev This contract does not custody USDT, mint tokens, or release source
///      escrow. Source escrow release remains governed by its own threshold
///      attestor policy. There is deliberately no owner or withdrawal method.
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
    error NativeTransferFailed();

    modifier nonReentrant() {
        if (entered != 1) revert ReentrantCall();
        entered = 2;
        _;
        entered = 1;
    }

    /// @notice Atomically forwards solver-supplied native SOBY to the user.
    /// @param orderId Unique cross-chain order identifier shared with source escrow.
    /// @param sourceChain Canonical bytes32 identifier for TRON/Ethereum/Solana.
    /// @param sourceEscrow Source escrow address/program identifier, left-padded
    ///        for 20-byte EVM/TVM addresses or used directly for 32-byte Solana keys.
    /// @param sourceAsset Source USDT contract/mint identifier.
    /// @param sourceAmount Exact source-chain USDT amount in its smallest units.
    /// @param recipient SOBYA EVM address that receives native SOBY.
    function executePayout(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount,
        address payable recipient
    ) external payable nonReentrant {
        if (
            orderId == bytes32(0) || sourceChain == bytes32(0) ||
            sourceEscrow == bytes32(0) || sourceAsset == bytes32(0) ||
            sourceAmount == 0 || recipient == address(0) ||
            msg.value == 0 || msg.value > type(uint128).max
        ) revert InvalidPayout();
        if (orderStatus[orderId] != Status.NONE) revert OrderAlreadyPaid();

        // Effects before interaction; a failed native transfer reverts all state.
        orderStatus[orderId] = Status.PAID;
        payouts[orderId] = Payout({
            sourceChain: sourceChain,
            sourceEscrow: sourceEscrow,
            sourceAsset: sourceAsset,
            sourceAmount: sourceAmount,
            recipient: recipient,
            sobyAmount: msg.value,
            solver: msg.sender,
            destinationChainId: block.chainid
        });

        (bool ok,) = recipient.call{value: msg.value}("");
        if (!ok) revert NativeTransferFailed();

        emit PayoutExecuted(
            orderId, sourceChain, sourceEscrow, sourceAsset, sourceAmount,
            recipient, msg.value, msg.sender, block.chainid
        );
    }
}
