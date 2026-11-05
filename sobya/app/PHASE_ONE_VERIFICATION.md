# SOBYA phase-one verification gates

This file defines the exact CI evidence required before phase one is marked complete. It does not change consensus behavior, tokenomics, genesis state, or production configuration.

## Required checks on one identical feature-branch commit

- Feature validation: dependency verification, full Go tests, and node builds for both the working source and archived source.
- EVM JSON-RPC smoke: node startup, chain/network identifiers, block production, signed EVM transfer and receipt, Solidity deployment/read/write, ERC-20 behavior, WebSocket subscription, and bank precompile balance read.
- Single-node localnet: 18-decimal asobya initialization, CometBFT block production, bank queries, and native-supply checks.
- Multi-node localnet: independent validator nodes, peer connectivity, consensus progress, and transaction propagation.
- Fee-routing integration: committed Cosmos/EVM fee transactions, exact 50/20/30 routing accounting, and no duplicate routing on subsequent empty blocks.
- Validator-reserve audit: focused reserve tests, uncached full Go test suite, and node build.

## Completion rule

Phase one is complete only when every required workflow above has a completed successful run against the same current feature-branch HEAD, and each job's substantive test steps are successful. A runner-allocation failure is infrastructure failure, not a code-test result. Historical successes on older commits do not satisfy this gate.

## Explicitly outside phase one

Two-chain IBC/ERC-20 packet interoperability, production genesis/address approval, production chain ID, external validator operations, production RPC hosting, security review, and public network launch remain later release gates. No production launch is authorized by passing CI.

All changes and checks remain on feature/tokenomics-fee-split; do not merge the draft pull request or modify main as part of this verification.