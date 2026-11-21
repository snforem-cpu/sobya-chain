// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SOBYA Solver Inventory Vault
/// @notice Custodies native SOBY and prevents withdrawals from consuming funds
///         reserved for outstanding cross-chain orders.
/// @dev This vault locks inventory, but does not prove source-chain deposits.
///      Source escrow attestors must still verify the destination payout event.
contract SobyaSolverInventoryVault {
    struct Reservation {
        address solver;
        address payable recipient;
        uint128 amount;
        uint64 releaseAfter;
        bool active;
    }

    mapping(address => uint256) public balances;
    mapping(address => uint256) public reserved;
    mapping(bytes32 => Reservation) public reservations;
    uint256 private entered = 1;

    event Deposited(address indexed solver, uint256 amount);
    event Withdrawn(address indexed solver, address indexed recipient, uint256 amount);
    event InventoryReserved(bytes32 indexed orderId, address indexed solver, address indexed recipient, uint256 amount, uint64 releaseAfter);
    event ReservationSettled(bytes32 indexed orderId, address indexed solver, address indexed recipient, uint256 amount);
    event ReservationReleased(bytes32 indexed orderId, address indexed solver, uint256 amount);

    error InvalidAmount();
    error InvalidReservation();
    error InsufficientAvailableInventory();
    error ReservationAlreadyExists();
    error ReservationNotActive();
    error ReservationNotExpired();
    error ReservationExpired();
    error UnauthorizedSolver();
    error NativeTransferFailed();
    error ReentrantCall();

    modifier nonReentrant() {
        if (entered != 1) revert ReentrantCall();
        entered = 2;
        _;
        entered = 1;
    }

    receive() external payable {
        _deposit(msg.sender, msg.value);
    }

    function deposit() external payable {
        _deposit(msg.sender, msg.value);
    }

    function _deposit(address solver, uint256 amount) private {
        if (amount == 0) revert InvalidAmount();
        balances[solver] += amount;
        emit Deposited(solver, amount);
    }

    function available(address solver) public view returns (uint256) {
        return balances[solver] - reserved[solver];
    }

    /// @notice Lock part of the caller's deposited SOBY for one immutable order.
    function reserve(
        bytes32 orderId,
        address payable recipient,
        uint128 amount,
        uint64 releaseAfter
    ) external {
        if (orderId == bytes32(0) || recipient == address(0) || amount == 0
            || releaseAfter <= block.timestamp) revert InvalidReservation();
        if (reservations[orderId].active || reservations[orderId].solver != address(0)) {
            revert ReservationAlreadyExists();
        }
        if (available(msg.sender) < amount) revert InsufficientAvailableInventory();
        reserved[msg.sender] += amount;
        reservations[orderId] = Reservation({
            solver: msg.sender,
            recipient: recipient,
            amount: amount,
            releaseAfter: releaseAfter,
            active: true
        });
        emit InventoryReserved(orderId, msg.sender, recipient, amount, releaseAfter);
    }

    /// @notice Anyone may trigger payout, but funds can only go to the reserved recipient.
    ///         This intentionally allows a funded order to complete if the solver is offline.
    function executePayout(bytes32 orderId) external nonReentrant {
        Reservation storage r = reservations[orderId];
        if (!r.active) revert ReservationNotActive();
        if (block.timestamp >= r.releaseAfter) revert ReservationExpired();

        address solver = r.solver;
        address payable recipient = r.recipient;
        uint256 amount = r.amount;
        r.active = false;
        reserved[solver] -= amount;
        balances[solver] -= amount;

        (bool ok,) = recipient.call{value: amount}("");
        if (!ok) revert NativeTransferFailed();
        emit ReservationSettled(orderId, solver, recipient, amount);
    }

    /// @notice Release a reservation only after its deadline; it never pays the solver.
    ///         Source escrow refund remains governed by its own on-chain deadline.
    function releaseExpired(bytes32 orderId) external {
        Reservation storage r = reservations[orderId];
        if (!r.active) revert ReservationNotActive();
        if (block.timestamp < r.releaseAfter) revert ReservationNotExpired();

        address solver = r.solver;
        uint256 amount = r.amount;
        r.active = false;
        reserved[solver] -= amount;
        emit ReservationReleased(orderId, solver, amount);
    }

    /// @notice Withdraw only unreserved inventory.
    function withdraw(address payable recipient, uint256 amount) external nonReentrant {
        if (recipient == address(0) || amount == 0) revert InvalidAmount();
        if (available(msg.sender) < amount) revert InsufficientAvailableInventory();
        balances[msg.sender] -= amount;
        (bool ok,) = recipient.call{value: amount}("");
        if (!ok) revert NativeTransferFailed();
        emit Withdrawn(msg.sender, recipient, amount);
    }
}
