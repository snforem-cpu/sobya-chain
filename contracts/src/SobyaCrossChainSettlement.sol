// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaSolverInventoryVault {
    function reservations(bytes32 orderId) external view returns (
        address solver, address recipient, uint128 amount, uint64 releaseAfter, bool active
    );
    function executePayout(bytes32 orderId) external;
}

/// @title SOBYA Cross-Chain Settlement
/// @notice Executes a payout only from SOBY already reserved in the inventory vault.
/// @dev Source-chain attestors must still verify this event before releasing USDT.
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

    ISobyaSolverInventoryVault public immutable inventoryVault;
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

    modifier nonReentrant() {
        if (entered != 1) revert ReentrantCall();
        entered = 2;
        _;
        entered = 1;
    }

    constructor(ISobyaSolverInventoryVault vault) {
        if (address(vault) == address(0)) revert InvalidPayout();
        inventoryVault = vault;
    }

    /// @notice Pays the exact recipient and amount previously locked in the vault.
    /// @dev Anyone may relay the call; the recipient and solver cannot be changed.
    function executePayout(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount
    ) external nonReentrant {
        if (
            orderId == bytes32(0) || sourceChain == bytes32(0) ||
            sourceEscrow == bytes32(0) || sourceAsset == bytes32(0) ||
            sourceAmount == 0
        ) revert InvalidPayout();
        if (orderStatus[orderId] != Status.NONE) revert OrderAlreadyPaid();

        (address solver, address recipient, uint128 amount, uint64 releaseAfter, bool active) =
            inventoryVault.reservations(orderId);
        if (!active || solver == address(0) || recipient == address(0)
            || amount == 0 || block.timestamp >= releaseAfter) {
            revert ReservationUnavailable();
        }

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
}
