// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaSolverInventoryVault.sol";
import "../src/SobyaCrossChainSettlement.sol";

interface VmDeploy {
    function envUint(string calldata key) external returns (uint256);
    function envAddress(string calldata key) external returns (address);
    function startBroadcast(uint256 privateKey) external;
    function stopBroadcast() external;
}

/// @notice Deploy the SOBYA native-SOBY inventory vault and its settlement gate.
/// @dev Run only with a locally supplied deployer key and three distinct
///      SOBYA-controlled attestor addresses. This script never embeds secrets.
contract DeploySobyaInventory {
    VmDeploy private constant vm =
        VmDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    uint256 private constant SOBYA_EVM_CHAIN_ID = 357812033857;

    function run() external returns (
        SobyaSolverInventoryVault vault,
        SobyaCrossChainSettlement settlement
    ) {
        require(block.chainid == SOBYA_EVM_CHAIN_ID, "wrong SOBYA EVM chain");

        uint256 deployerKey = vm.envUint("SOBYA_DEPLOYER_PRIVATE_KEY");
        address[] memory attestors = new address[](3);
        attestors[0] = vm.envAddress("SOBYA_ATTESTOR_1");
        attestors[1] = vm.envAddress("SOBYA_ATTESTOR_2");
        attestors[2] = vm.envAddress("SOBYA_ATTESTOR_3");

        vm.startBroadcast(deployerKey);
        vault = new SobyaSolverInventoryVault();
        settlement = new SobyaCrossChainSettlement(
            ISobyaSolverInventoryVault(address(vault)),
            attestors,
            2
        );
        vault.setSettlement(address(settlement));
        vm.stopBroadcast();

        require(vault.owner() != address(0), "vault owner missing");
        require(vault.settlement() == address(settlement), "vault settlement link mismatch");
        require(address(settlement.inventoryVault()) == address(vault), "settlement vault link mismatch");
        require(settlement.attestationThreshold() == 2, "unexpected attestor threshold");
    }
}
