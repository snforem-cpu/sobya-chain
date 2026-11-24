// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20DepositToken {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @title SOBYA cross-chain deposit escrow
/// @notice Holds an exact ERC-20 payment until the operator confirms the SOBYA
///         payout. A depositor can reclaim an unfulfilled order after its deadline.
/// @dev Deploy on Ethereum with the canonical USDT contract. This contract does
///      not bridge assets or verify SOBYA finality; the authorized operator must
///      call markFulfilled only after independently verifying the destination payout.
contract SobyaCrossChainDeposit {

    struct Order {
        address depositor;
        address recipient;
        uint128 paymentAmount;
        uint128 sobyAmount;
        uint64 deadline;
        bool fulfilled;
        bool refunded;
        bool paymentReleased;
    }

    IERC20DepositToken public immutable paymentToken;
    address public immutable operator;
    address public immutable treasury;
    mapping(bytes32 => Order) public orders;

    event OrderDeposited(
        bytes32 indexed orderId,
        address indexed depositor,
        address indexed recipient,
        uint256 paymentAmount,
        uint256 sobyAmount,
        uint64 deadline
    );
    event OrderFulfilled(bytes32 indexed orderId);
    event PaymentReleased(bytes32 indexed orderId, address indexed recipient, uint256 amount);
    event OrderRefunded(bytes32 indexed orderId, address indexed depositor, uint256 amount);

    error Unauthorized();
    error InvalidOrder();
    error AlreadyProcessed();
    error TransferFailed();
    error InexactTokenTransfer();

    constructor(address token, address operator_, address treasury_) {
        if (token == address(0) || operator_ == address(0) || treasury_ == address(0)) revert InvalidOrder();
        paymentToken = IERC20DepositToken(token);
        operator = operator_;
        treasury = treasury_;
    }

    function deposit(
        bytes32 orderId,
        address recipient,
        uint128 paymentAmount,
        uint128 sobyAmount,
        uint64 deadline
    ) external {
        if (
            orderId == bytes32(0) || recipient == address(0) ||
            paymentAmount == 0 || sobyAmount == 0 ||
            deadline <= block.timestamp || orders[orderId].depositor != address(0)
        ) revert InvalidOrder();

        uint256 beforeBalance = paymentToken.balanceOf(address(this));
        if (!paymentToken.transferFrom(msg.sender, address(this), paymentAmount)) revert TransferFailed();
        uint256 received = paymentToken.balanceOf(address(this)) - beforeBalance;
        if (received != paymentAmount) revert InexactTokenTransfer();

        orders[orderId] = Order({
            depositor: msg.sender,
            recipient: recipient,
            paymentAmount: paymentAmount,
            sobyAmount: sobyAmount,
            deadline: deadline,
            fulfilled: false,
            refunded: false,
            paymentReleased: false
        });

        emit OrderDeposited(orderId, msg.sender, recipient, paymentAmount, sobyAmount, deadline);
    }

    function markFulfilled(bytes32 orderId) external {
        if (msg.sender != operator) revert Unauthorized();
        Order storage order = orders[orderId];
        if (order.depositor == address(0) || order.fulfilled || order.refunded) revert AlreadyProcessed();
        order.fulfilled = true;
        emit OrderFulfilled(orderId);
    }

    function releasePayment(bytes32 orderId) external {
        if (msg.sender != operator) revert Unauthorized();
        Order storage order = orders[orderId];
        if (
            !order.fulfilled || order.refunded || order.paymentReleased
        ) revert AlreadyProcessed();
        order.paymentReleased = true;
        if (!paymentToken.transfer(treasury, order.paymentAmount)) revert TransferFailed();
        emit PaymentReleased(orderId, treasury, order.paymentAmount);
    }

    function refund(bytes32 orderId) external {
        Order storage order = orders[orderId];
        if (order.depositor != msg.sender || order.fulfilled || order.refunded ||
            order.paymentReleased || block.timestamp <= order.deadline) revert InvalidOrder();
        order.refunded = true;
        if (!paymentToken.transfer(order.depositor, order.paymentAmount)) revert TransferFailed();
        emit OrderRefunded(orderId, order.depositor, order.paymentAmount);
    }
}
