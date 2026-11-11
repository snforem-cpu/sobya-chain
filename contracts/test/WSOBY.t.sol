// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/WSOBY.sol";

interface Vm {
    function deal(address account, uint256 newBalance) external;
    function prank(address sender) external;
}

contract WSOBYTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    WSOBY private token;

    receive() external payable {}

    function setUp() public {
        token = new WSOBY();
        vm.deal(address(this), 100 ether);
    }

    function testMetadataAndNoPremint() public view {
        require(keccak256(bytes(token.name())) == keccak256(bytes("Wrapped SOBYA")), "wrong name");
        require(keccak256(bytes(token.symbol())) == keccak256(bytes("WSOBY")), "wrong symbol");
        require(token.decimals() == 18, "wrong decimals");
        require(token.totalSupply() == 0, "unexpected premint");
        require(address(token).balance == 0, "unexpected backing");
    }

    function testDepositMintsExactlyOneToOne() public {
        token.deposit{value: 2 ether}();
        require(token.balanceOf(address(this)) == 2 ether, "wrong minted balance");
        require(token.totalSupply() == 2 ether, "wrong supply");
        require(address(token).balance == token.totalSupply(), "backing mismatch");
    }

    function testReceiveFallbackWrapsNativeSOBY() public {
        (bool ok, ) = address(token).call{value: 3 ether}("");
        require(ok, "receive deposit failed");
        require(token.balanceOf(address(this)) == 3 ether, "receive did not mint");
        require(address(token).balance == token.totalSupply(), "backing mismatch");
    }

    function testWithdrawBurnsAndReturnsNativeSOBY() public {
        token.deposit{value: 4 ether}();
        uint256 beforeBalance = address(this).balance;
        token.withdraw(1 ether);
        require(address(this).balance == beforeBalance + 1 ether, "native SOBY not returned");
        require(token.balanceOf(address(this)) == 3 ether, "wrong remaining balance");
        require(token.totalSupply() == 3 ether, "wrong remaining supply");
        require(address(token).balance == token.totalSupply(), "backing mismatch");
    }

    function testTransferAndTransferFrom() public {
        address alice = address(0xA11CE);
        token.deposit{value: 5 ether}();
        require(token.transfer(alice, 1 ether), "transfer failed");
        require(token.balanceOf(alice) == 1 ether, "wrong recipient balance");
        token.approve(alice, 2 ether);
        vm.prank(alice);
        require(token.transferFrom(address(this), alice, 2 ether), "transferFrom failed");
        require(token.balanceOf(alice) == 3 ether, "wrong transferFrom balance");
        require(token.allowance(address(this), alice) == 0, "allowance not reduced");
        require(token.totalSupply() == 5 ether, "transfer changed supply");
        require(address(token).balance == token.totalSupply(), "backing mismatch");
    }

    function testCannotWithdrawMoreThanBalance() public {
        token.deposit{value: 1 ether}();
        (bool ok, ) = address(token).call(abi.encodeCall(WSOBY.withdraw, (2 ether)));
        require(!ok, "over-withdraw unexpectedly succeeded");
        require(token.totalSupply() == 1 ether, "failed withdraw changed supply");
        require(address(token).balance == 1 ether, "failed withdraw changed backing");
    }

    function testFuzzDepositWithdraw(uint96 rawAmount) public {
        uint256 amount = uint256(rawAmount);
        vm.deal(address(this), amount);
        token.deposit{value: amount}();
        require(token.balanceOf(address(this)) == amount, "fuzz mint mismatch");
        require(token.totalSupply() == amount, "fuzz supply mismatch");
        token.withdraw(amount);
        require(token.balanceOf(address(this)) == 0, "fuzz burn mismatch");
        require(token.totalSupply() == 0, "fuzz supply not zero");
        require(address(token).balance == 0, "fuzz backing not zero");
    }
}
