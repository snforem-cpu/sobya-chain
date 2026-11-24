// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SOBYA inventory payout vault
/// @notice Holds native SOBY and releases one payout per verified source order.
/// @dev The relayer must be a narrowly scoped automation key. This contract
///      prevents replay and enforces per-order and daily payout caps. It does not
///      itself verify Ethereum deposits; only the configured relayer can release.
contract SobyaInventoryPayoutVault {
    address public immutable owner;
    address public relayer;
    bool public paused;
    uint256 public maxPayoutPerOrder;
    uint256 public dailyPayoutLimit;
    uint256 public currentDay;
    uint256 public paidToday;

    mapping(bytes32 => bool) public processedOrders;

    event PayoutReleased(bytes32 indexed orderId, address indexed recipient, uint256 amount);
    event RelayerUpdated(address indexed previousRelayer, address indexed newRelayer);
    event LimitsUpdated(uint256 maxPayoutPerOrder, uint256 dailyPayoutLimit);
    event PauseUpdated(bool paused);
    event Funded(address indexed sender, uint256 amount);

    error Unauthorized();
    error InvalidPayout();
    error OrderAlreadyProcessed();
    error LimitExceeded();
    error TransferFailed();

    constructor(address relayer_, uint256 maxPerOrder_, uint256 dailyLimit_) {
        if (relayer_ == address(0) || maxPerOrder_ == 0 || dailyLimit_ < maxPerOrder_) {
            revert InvalidPayout();
        }
        owner = msg.sender;
        relayer = relayer_;
        maxPayoutPerOrder = maxPerOrder_;
        dailyPayoutLimit = dailyLimit_;
    }

    receive() external payable {
        emit Funded(msg.sender, msg.value);
    }

    function release(bytes32 orderId, address payable recipient, uint256 amount) external {
        if (msg.sender != relayer) revert Unauthorized();
        if (paused) revert InvalidPayout();
        if (orderId == bytes32(0) || recipient == address(0) || amount == 0) revert InvalidPayout();
        if (processedOrders[orderId]) revert OrderAlreadyProcessed();
        if (amount > maxPayoutPerOrder) revert LimitExceeded();

        uint256 day = block.timestamp / 1 days;
        if (day != currentDay) {
            currentDay = day;
            paidToday = 0;
        }
        if (paidToday + amount > dailyPayoutLimit) revert LimitExceeded();
        if (address(this).balance < amount) revert TransferFailed();

        processedOrders[orderId] = true;
        paidToday += amount;
        (bool ok,) = recipient.call{value: amount}("");
        if (!ok) revert TransferFailed();

        emit PayoutReleased(orderId, recipient, amount);
    }

    function setRelayer(address newRelayer) external {
        if (msg.sender != owner) revert Unauthorized();
        if (newRelayer == address(0)) revert InvalidPayout();
        emit RelayerUpdated(relayer, newRelayer);
        relayer = newRelayer;
    }

    function setLimits(uint256 maxPerOrder, uint256 dailyLimit) external {
        if (msg.sender != owner) revert Unauthorized();
        if (maxPerOrder == 0 || dailyLimit < maxPerOrder) revert InvalidPayout();
        maxPayoutPerOrder = maxPerOrder;
        dailyPayoutLimit = dailyLimit;
        emit LimitsUpdated(maxPerOrder, dailyLimit);
    }

    function setPaused(bool value) external {
        if (msg.sender != owner) revert Unauthorized();
        paused = value;
        emit PauseUpdated(value);
    }
}
