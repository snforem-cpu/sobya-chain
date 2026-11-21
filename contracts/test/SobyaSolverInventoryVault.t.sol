// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaSolverInventoryVault.sol";

interface VmInventoryVault {
    function deal(address account, uint256 newBalance) external;
    function warp(uint256 timestamp) external;
}

contract RejectInventoryRecipient {
    receive() external payable { revert("reject"); }
}

contract SobyaSolverInventoryVaultTest {
    VmInventoryVault private constant vm = VmInventoryVault(address(uint160(uint256(keccak256("hevm cheat code")))));
    SobyaSolverInventoryVault private vault;

    function setUp() public {
        vault = new SobyaSolverInventoryVault();
        vm.deal(address(this), 20 ether);
    }

    function testReservedInventoryCannotBeWithdrawn() public {
        vault.deposit{value: 5 ether}();
        vault.reserve(keccak256("order-1"), payable(address(0xBEEF)), 3 ether, uint64(block.timestamp + 1 days));
        require(vault.available(address(this)) == 2 ether, "available mismatch");
        (bool ok,) = address(vault).call(abi.encodeWithSelector(vault.withdraw.selector, payable(address(this)), 3 ether));
        require(!ok, "reserved balance withdrawn");
        require(vault.reserved(address(this)) == 3 ether, "reservation lost");
    }

    function testAnyoneCanSettleOnlyToReservedRecipient() public {
        address payable recipient = payable(address(0xBEEF));
        vault.deposit{value: 5 ether}();
        bytes32 orderId = keccak256("order-2");
        vault.reserve(orderId, recipient, 2 ether, uint64(block.timestamp + 1 days));
        uint256 beforeBalance = recipient.balance;
        vault.executePayout(orderId);
        require(recipient.balance == beforeBalance + 2 ether, "recipient not paid");
        require(vault.balances(address(this)) == 3 ether, "solver balance mismatch");
        require(vault.reserved(address(this)) == 0, "reservation not consumed");
        (bool ok,) = address(vault).call(abi.encodeWithSelector(vault.executePayout.selector, orderId));
        require(!ok, "duplicate payout accepted");
    }

    function testExpiredReservationCanBeReleasedButNotPaid() public {
        vault.deposit{value: 4 ether}();
        bytes32 orderId = keccak256("order-3");
        uint64 deadline = uint64(block.timestamp + 1 hours);
        vault.reserve(orderId, payable(address(0xBEEF)), 3 ether, deadline);
        vm.warp(deadline);
        (bool payoutOk,) = address(vault).call(abi.encodeWithSelector(vault.executePayout.selector, orderId));
        require(!payoutOk, "expired payout accepted");
        vault.releaseExpired(orderId);
        require(vault.reserved(address(this)) == 0, "reservation not released");
        require(vault.available(address(this)) == 4 ether, "available balance mismatch");
    }

    function testCannotReserveMoreThanAvailable() public {
        vault.deposit{value: 1 ether}();
        (bool ok,) = address(vault).call(abi.encodeWithSelector(
            vault.reserve.selector, keccak256("oversubscribed"), payable(address(0xBEEF)),
            uint128(1 ether + 1), uint64(block.timestamp + 1 days)
        ));
        require(!ok, "oversubscription accepted");
    }

    function testFailedRecipientTransferRollsBackReservation() public {
        vault.deposit{value: 2 ether}();
        RejectInventoryRecipient recipient = new RejectInventoryRecipient();
        bytes32 orderId = keccak256("order-4");
        vault.reserve(orderId, payable(address(recipient)), 1 ether, uint64(block.timestamp + 1 days));
        (bool ok,) = address(vault).call(abi.encodeWithSelector(vault.executePayout.selector, orderId));
        require(!ok, "rejecting recipient unexpectedly paid");
        require(vault.reserved(address(this)) == 1 ether, "reservation not restored");
        require(vault.balances(address(this)) == 2 ether, "balance not restored");
    }
}
