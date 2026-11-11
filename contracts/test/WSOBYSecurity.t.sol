// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/WSOBY.sol";

interface VmSecurity {
    function deal(address account, uint256 newBalance) external;
}

contract RejectingNativeRecipient {
    WSOBY private immutable token;

    constructor(WSOBY token_) {
        token = token_;
    }

    function wrap() external payable {
        token.deposit{value: msg.value}();
    }

    function redeem(uint256 amount) external {
        token.withdraw(amount);
    }

    receive() external payable {
        revert("recipient rejects native coin");
    }
}

contract ReentrantNativeRecipient {
    WSOBY private immutable token;
    uint256 public reentryAttempts;

    constructor(WSOBY token_) {
        token = token_;
    }

    function wrap() external payable {
        token.deposit{value: msg.value}();
    }

    function redeem(uint256 amount) external {
        token.withdraw(amount);
    }

    receive() external payable {
        reentryAttempts += 1;
        (bool success, ) = address(token).call(
            abi.encodeWithSelector(token.withdraw.selector, msg.value)
        );
        require(!success, "reentrant withdrawal unexpectedly succeeded");
    }
}

contract WSOBYSecurityTest {
    VmSecurity private constant vm =
        VmSecurity(address(uint160(uint256(keccak256("hevm cheat code")))));

    WSOBY private token;

    function setUp() public {
        token = new WSOBY();
        vm.deal(address(this), 2 ether);
    }

    function testWithdrawalFailurePreservesWrappedBalanceAndBacking() public {
        RejectingNativeRecipient recipient = new RejectingNativeRecipient(token);
        recipient.wrap{value: 1 ether}();

        (bool success, ) = address(recipient).call(
            abi.encodeWithSelector(recipient.redeem.selector, 1 ether)
        );

        require(!success, "withdrawal to rejecting recipient unexpectedly succeeded");
        require(token.balanceOf(address(recipient)) == 1 ether, "wrapped balance was not restored");
        require(token.totalSupply() == 1 ether, "total supply changed after failed withdrawal");
        require(address(token).balance == 1 ether, "native backing changed after failed withdrawal");
    }

    function testReentrantRecipientCannotWithdrawMoreThanItsBurnedBalance() public {
        ReentrantNativeRecipient recipient = new ReentrantNativeRecipient(token);
        recipient.wrap{value: 1 ether}();

        recipient.redeem(1 ether);

        require(recipient.reentryAttempts() == 1, "recipient callback did not execute");
        require(token.balanceOf(address(recipient)) == 0, "wrapped balance remains after full withdrawal");
        require(token.totalSupply() == 0, "total supply remains after full withdrawal");
        require(address(token).balance == 0, "native backing remains after full withdrawal");
        require(address(recipient).balance == 1 ether, "recipient did not receive native coin");
    }
}
