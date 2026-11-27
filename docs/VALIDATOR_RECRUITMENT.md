# SOBYA Independent Validator Recruitment

**Status: SOBYA Mainnet is live. This document describes joining the existing network, not pre-launch recruitment.**

SOBYA operates a public Cosmos SDK / CometBFT mainnet with Cosmos EVM enabled. Independent operators may apply to join as additional validators or full nodes. Each operator controls their own Linux host and keeps their own signing keys.

## Recruitment target

The initial target is four independent validator operators, plus one non-validator RPC/full-node operator. A separate seed node is useful. Operators should be distributed across providers/networks where practical.

Operators should be able to provide:
- Persistent Linux infrastructure and reliable power/network.
- Public inbound TCP P2P connectivity (normally port 26656).
- SSD capacity, time synchronization, monitoring, backups, and routine maintenance.
- Experience with Linux operations; Cosmos SDK / CometBFT experience is preferred.

The operator pays for and controls their own infrastructure. No reimbursement, financial return, token price, or guaranteed reward is promised. Validator distributions follow the protocol reserve and signing-eligibility rules; no fiat return, market price, liquidity, exchange listing, or infrastructure reimbursement is promised.

## Safe participation

Each operator creates account, node, and private-validator keys locally. Never send mnemonic phrases, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json` to the project. During live-chain onboarding, share only the public account address, public node information and other details explicitly requested by the operator coordinator.

## Joining the live network

Interested operators may submit an expression of interest using the public application template in [the recruitment publication pack](ANNOUNCEMENTS.md). Application review is manual and does not itself create a validator.

SOBYA Mainnet is already running. A new operator must use the existing live chain, synchronize from verified peers, confirm the current release and on-chain staking parameters, and create its validator with the supported live-chain transaction. Do not create production gentxs, propose a replacement genesis, or start a separate chain.

## Required reading

- [Complete operator onboarding kit](STAGE_THREE_OPERATOR_KIT.md)
- [Genesis ceremony](GENESIS_CEREMONY.md)
- [Release process](RELEASE_PROCESS.md)
- [Ready-to-publish X and Telegram messages](ANNOUNCEMENTS.md)
- [P2P/RPC security and connectivity](testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

## Live-network operating checks

Before an operator creates a validator, verify the current binary release, CometBFT chain ID `sobya-1`, EVM chain ID `357812033857`, public peer information, current staking parameters, minimum self-delegation and transaction fees. Public endpoints are listed in the repository [README](../README.md).

No placeholder IDs, peer addresses, genesis files or RPC URLs may be presented as live. Validator rewards follow protocol rules and are not a promise of fiat income, market price, liquidity, exchange listing or infrastructure reimbursement.
