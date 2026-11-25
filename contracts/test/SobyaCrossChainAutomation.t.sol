// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaCrossChainDeposit.sol";
import "../src/SobyaInventoryPayoutVault.sol";

interface VmCrossChain {
    function deal(address account, uint256 newBalance) external;
    function warp(uint256 timestamp) external;
    function prank(address sender) external;
}

contract MockDepositToken is IERC20DepositToken {
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external { balanceOf[to] += amount; }
    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }
    function transfer(address to, uint256 amount) external override returns (bool) {
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }
    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        require(allowance[from][msg.sender] >= amount, "allowance");
        require(balanceOf[from] >= amount, "balance");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract SobyaCrossChainAutomationTest {
    VmCrossChain private constant vm =
        VmCrossChain(address(uint160(uint256(keccak256("hevm cheat code")))));

    address private constant OPERATOR = address(0xA11CE);
    address private constant TREASURY = address(0x7EA5);
    address private constant RELAYER = address(0xB0B);
    address private constant BUYER = address(0xCAFE);
    address private constant RECIPIENT = address(0xD00D);
    bytes32 private constant ORDER = keccak256("sobya-test-order");

    MockDepositToken private token;
    SobyaCrossChainDeposit private escrow;
    SobyaInventoryPayoutVault private vault;

    function setUp() public {
        token = new MockDepositToken();
        escrow = new SobyaCrossChainDeposit(address(token), OPERATOR, TREASURY);
        vault = new SobyaInventoryPayoutVault(RELAYER, 15 ether, 20 ether);
        vm.deal(address(this), 20 ether);
        vm.deal(address(vault), 20 ether);
        token.mint(BUYER, 10_000_000);
    }

    function testDepositFulfillmentAndPaymentRelease() public {
        vm.prank(BUYER);
        token.approve(address(escrow), 1_000_000);
        vm.prank(BUYER);
        escrow.deposit(ORDER, RECIPIENT, 1_000_000, 200 ether, uint64(block.timestamp + 1 days));

        require(token.balanceOf(address(escrow)) == 1_000_000, "escrow did not receive payment");
        vm.prank(OPERATOR);
        escrow.markFulfilled(ORDER);
        vm.prank(OPERATOR);
        escrow.releasePayment(ORDER);
        require(token.balanceOf(TREASURY) == 1_000_000, "payment not released to fixed treasury");
    }

    function testUnfulfilledOrderCanBeRefundedAfterDeadline() public {
        vm.prank(BUYER);
        token.approve(address(escrow), 1_000_000);
        uint64 deadline = uint64(block.timestamp + 1 hours);
        vm.prank(BUYER);
        escrow.deposit(ORDER, RECIPIENT, 1_000_000, 200 ether, deadline);
        vm.warp(uint256(deadline) + 1);
        vm.prank(BUYER);
        escrow.refund(ORDER);
        require(token.balanceOf(BUYER) == 10_000_000, "buyer was not refunded");
    }

    function testPayoutVaultReleasesOnceAndRejectsReplay() public {
        vm.prank(RELAYER);
        vault.release(ORDER, payable(RECIPIENT), 1 ether);
        require(RECIPIENT.balance == 1 ether, "recipient did not receive SOBY");
        require(vault.processedOrders(ORDER), "order not marked processed");
        vm.prank(RELAYER);
        (bool success,) = address(vault).call(
            abi.encodeWithSelector(vault.release.selector, ORDER, payable(RECIPIENT), 1 ether)
        );
        require(!success, "duplicate payout unexpectedly succeeded");
        require(RECIPIENT.balance == 1 ether, "duplicate payment occurred");
    }

    function testPayoutVaultEnforcesPerOrderAndDailyLimits() public {
        vm.prank(RELAYER);
        (bool tooLarge,) = address(vault).call(
            abi.encodeWithSelector(vault.release.selector, ORDER, payable(RECIPIENT), 16 ether)
        );
        require(!tooLarge, "per-order limit was bypassed");

        vm.prank(RELAYER);
        vault.release(ORDER, payable(RECIPIENT), 10 ether);
        bytes32 secondOrder = keccak256("second-order");
        vm.prank(RELAYER);
        (bool dailyExceeded,) = address(vault).call(
            abi.encodeWithSelector(vault.release.selector, secondOrder, payable(RECIPIENT), 11 ether)
        );
        require(!dailyExceeded, "daily limit was bypassed");
    }

    function testOnlyConfiguredRelayerCanRelease() public {
        (bool success,) = address(vault).call(
            abi.encodeWithSelector(vault.release.selector, ORDER, payable(RECIPIENT), 1 ether)
        );
        require(!success, "unauthorized payout unexpectedly succeeded");
    }
}
