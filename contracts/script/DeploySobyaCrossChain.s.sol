// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaSolverInventoryVault.sol";
import "../src/SobyaCrossChainSettlement.sol";

interface VmCrossChainDeploy {
    function startBroadcast() external;
    function stopBroadcast() external;
    function envAddress(string calldata name) external returns (address);
    function envBool(string calldata name) external returns (bool);
}

/// @notice Owner-run deployment of the SOBYA inventory vault and settlement pair.
/// @dev This script never contains keys. Foundry uses the owner's local keystore.
///      Deployment is blocked unless an explicit local environment approval is set.
contract DeploySobyaCrossChain {
    VmCrossChainDeploy private constant vm =
        VmCrossChainDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    event CrossChainDeployment(address indexed inventoryVault, address indexed settlement,
        address attestor1, address attestor2, address attestor3);

    function run() external {
        require(block.chainid == 357812033857, "SOBYA CROSS-CHAIN: WRONG_CHAIN_ID");
        require(
            vm.envBool("SOBYA_CROSS_CHAIN_DEPLOYMENT_APPROVED"),
            "SOBYA CROSS-CHAIN: OWNER_APPROVAL_REQUIRED"
        );

        address attestor1 = vm.envAddress("SOBYA_ATTESTOR_1");
        address attestor2 = vm.envAddress("SOBYA_ATTESTOR_2");
        address attestor3 = vm.envAddress("SOBYA_ATTESTOR_3");
        require(
            attestor1 != address(0) && attestor2 != address(0) && attestor3 != address(0)
                && attestor1 != attestor2 && attestor1 != attestor3 && attestor2 != attestor3,
            "SOBYA CROSS-CHAIN: INVALID_ATTESTORS"
        );

        vm.startBroadcast();
        SobyaSolverInventoryVault vault = new SobyaSolverInventoryVault();
        address[] memory attestors = new address[](3);
        attestors[0] = attestor1;
        attestors[1] = attestor2;
        attestors[2] = attestor3;
        SobyaCrossChainSettlement settlement =
            new SobyaCrossChainSettlement(ISobyaSolverInventoryVault(address(vault)), attestors, 2);
        vm.stopBroadcast();

        emit CrossChainDeployment(
            address(vault), address(settlement), attestor1, attestor2, attestor3
        );
    }
}
