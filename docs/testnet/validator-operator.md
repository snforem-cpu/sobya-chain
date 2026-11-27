# Historical validator notes — use the live onboarding guide

SOBYA Mainnet is live. This historical path is retained for older links; current operators must use [the live validator onboarding guide](../validator-support/ONBOARDING.md) and [the operator kit](../STAGE_THREE_OPERATOR_KIT.md).

Production identifiers:
- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`

Public endpoints:
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- CometBFT RPC: `https://sobya-rpc.nodesafe-dapp.xyz`
- REST API: `https://sobya-api.nodesafe-dapp.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

A joining operator synchronizes to the existing chain and creates a validator through the supported live-chain transaction flow after confirming the current release, peers, staking parameters and fees. Do not use a draft genesis, local testnet chain ID, genesis gentx or guessed peer address.

Generate and retain all account, node and private-validator keys locally. Never send mnemonic phrases, keyrings, private keys, `priv_validator_key.json`, or `node_key.json` to the coordinator.
