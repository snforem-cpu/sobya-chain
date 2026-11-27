// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaProofRegistry.sol";

interface VmProofDeploy {
    function startBroadcast() external;
    function stopBroadcast() external;
    function envAddress(string calldata name) external returns (address);
}

/// @notice Deploys the standalone SOBYA Proof registry from a locally controlled wallet.
/// @dev Set PRIVATE_KEY and SOBYA_PROOF_FEE_RECIPIENT locally; never store either in GitHub.
contract DeploySobyaProof {
    VmProofDeploy private constant vm =
        VmProofDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    function run() external {
        require(block.chainid == 357812033857, "SOBYA_PROOF: WRONG_CHAIN_ID");
        address recipient = vm.envAddress("SOBYA_PROOF_FEE_RECIPIENT");
        vm.startBroadcast();
        new SobyaProofRegistry(recipient);
        vm.stopBroadcast();
    }
}
