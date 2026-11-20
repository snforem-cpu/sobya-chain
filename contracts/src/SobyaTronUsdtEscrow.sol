// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// The TRON deployment uses the same audited state-machine implementation as
// the Ethereum adapter. TVM execution still requires a TRON-solc build and
// Shasta testnet verification; this inheritance wrapper gives the deployment
// artifact an explicit chain-specific name without forking escrow logic.
import "./SobyaEthereumUsdtEscrow.sol";

/// @title SOBYA TRON USDT source escrow
/// @notice TRC-20 escrow wrapper. Deploy only after compiling with TRON's
///         Solidity distribution and validating the bytecode on Shasta.
/// @dev The inherited EIP-712 domain binds signatures to block.chainid and
///      this contract address, preventing cross-deployment replay.
contract SobyaTronUsdtEscrow is SobyaEthereumUsdtEscrow {
    constructor(address trc20Usdt_, address[] memory attestors_, uint256 threshold_)
        SobyaEthereumUsdtEscrow(trc20Usdt_, attestors_, threshold_)
    {}
}
