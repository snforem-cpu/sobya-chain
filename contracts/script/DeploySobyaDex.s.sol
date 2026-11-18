// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/WSOBY.sol";
import "../src/SobyaV2Factory.sol";
import "../src/SobyaV2Router.sol";

/// @notice Deploys the SOBYA wrapper and V2 AMM contracts from the caller's wallet.
/// @dev PRIVATE_KEY is read only from the local environment. Never put it in GitHub.
contract DeploySobyaDex is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        WSOBY wrapped = new WSOBY();
        SobyaV2Factory factory = new SobyaV2Factory();
        SobyaV2Router router = new SobyaV2Router(address(factory), address(wrapped));

        vm.stopBroadcast();

        console2.log("WSOBY:", address(wrapped));
        console2.log("SOBYA V2 Factory:", address(factory));
        console2.log("SOBYA V2 Router:", address(router));
        console2.log("Network EVM chain ID must be 357812033857");
    }
}
