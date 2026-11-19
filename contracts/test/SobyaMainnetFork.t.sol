// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/WSOBY.sol";
import "../src/SobyaV2Factory.sol";
import "../src/SobyaV2Router.sol";
import "../src/SobyaV2Oracle.sol";

interface VmMainnetFork {
    function deal(address account, uint256 newBalance) external;
}

/// @notice Deploys the DEX contracts inside a disposable Foundry fork of SOBYA Mainnet.
/// @dev This is simulation only: no broadcast, signing key, or mainnet transaction is used.
contract SobyaMainnetForkTest {
    VmMainnetFork private constant vm =
        VmMainnetFork(address(uint160(uint256(keccak256("hevm cheat code")))));

    function testDeployAndWireDexContractsOnSobyaMainnetFork() external {
        // The ordinary local suite runs on chain 31337; execute only in the explicit SOBYA fork job.\n        if (block.chainid != 357812033857) return;

        WSOBY wrapped = new WSOBY();
        SobyaV2Factory factory = new SobyaV2Factory();
        SobyaV2Oracle oracle = new SobyaV2Oracle(address(factory));
        SobyaV2Router router = new SobyaV2Router(address(factory), address(wrapped));

        require(address(wrapped).code.length > 0, "WSOBY_NOT_DEPLOYED");
        require(address(factory).code.length > 0, "FACTORY_NOT_DEPLOYED");
        require(address(oracle).code.length > 0, "ORACLE_NOT_DEPLOYED");
        require(address(router).code.length > 0, "ROUTER_NOT_DEPLOYED");
        require(oracle.factory() == address(factory), "ORACLE_FACTORY_MISMATCH");
        require(router.factory() == address(factory), "ROUTER_FACTORY_MISMATCH");
        require(router.wrappedSoby() == address(wrapped), "ROUTER_WRAPPED_MISMATCH");

        address pair = factory.createPair(address(0x1001), address(0x1002));
        require(pair.code.length > 0, "PAIR_NOT_DEPLOYED");
        require(factory.getPair(address(0x1001), address(0x1002)) == pair, "PAIR_NOT_REGISTERED");

        vm.deal(address(this), 1 ether);
        wrapped.deposit{value: 1 ether}();
        require(wrapped.balanceOf(address(this)) == 1 ether, "WSOBY_DEPOSIT_FAILED");
        wrapped.withdraw(1 ether);
        require(address(this).balance == 1 ether, "WSOBY_WITHDRAW_FAILED");
    }

    receive() external payable {}
}
