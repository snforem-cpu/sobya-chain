// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/WSOBY.sol";
import "../src/SobyaV2Factory.sol";
import "../src/SobyaV2Router.sol";

interface VmDeploy {
    function envUint(string calldata key) external returns (uint256);
    function startBroadcast(uint256 privateKey) external;
    function stopBroadcast() external;
}

/// @notice Deploys WSOBY, Factory and Router from the caller's local Foundry wallet.
/// @dev PRIVATE_KEY is read only from the local environment. Never put it in GitHub.
contract DeploySobyaDex {
    VmDeploy private constant vm = VmDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    event DeploymentAddresses(address indexed wrappedSoby, address indexed factory, address indexed router);

    function run() external {
        require(block.chainid == 357812033857, "SOBYA DEX: WRONG_CHAIN_ID");
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        WSOBY wrapped = new WSOBY();
        SobyaV2Factory factory = new SobyaV2Factory();
        SobyaV2Router router = new SobyaV2Router(address(factory), address(wrapped));

        emit DeploymentAddresses(address(wrapped), address(factory), address(router));
        vm.stopBroadcast();
    }
}
