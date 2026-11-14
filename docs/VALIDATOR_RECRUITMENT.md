# SOBYA Mainnet — Independent Validator Recruitment

**Status: SOBYA Mainnet is running. Independent validator applications are open.** This process adds operators to the existing chain; it is not a new genesis or testnet launch.

SOBYA currently has a live Cosmos SDK / CometBFT network with an EVM interface. Independent operators can first synchronize a full node, then register a validator through the live staking module when the binary, peer, self-delegation, and fee details below are verified.

## Recruitment target

Recruit independent validator operators across separate providers and networks where possible. Also welcome non-validator full-node, seed, and RPC operators. Each validator operator must control their own persistent Linux host and signing keys.

Applicants should provide:
- Persistent Linux infrastructure, reliable power/network, SSD storage, monitoring, backups, and maintenance.
- Public inbound P2P TCP reachability (normally port 26656).
- Experience with Linux operations; Cosmos SDK / CometBFT experience is preferred.

Operators pay for and control their own infrastructure. The project does not promise hosting reimbursement, fiat income, token price, liquidity, exchange listing, or guaranteed rewards.

## No project-funded validator transfers

Ordinary onboarding does not include SOBY grants or transfers from founder, treasury, liquidity, emergency, or validator-reserve wallets. Each operator must satisfy any live self-delegation and transaction-fee requirements from their own resources.

The project is checking whether the live chain accepts the minimum self-delegation of 1 asobya and zero Cosmos transaction fees. This is **not yet a public promise**: NodeSafe's existing validator reports `min_self_delegation=1`, but that alone does not prove the minimum for every new validator, and an EVM gas-price response of zero does not establish Cosmos SDK fee policy.

## Safe participation

Each operator generates account, node, and private-validator keys locally. Never send mnemonic phrases, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json` to the project. The project needs only public operator details, public account/operator addresses, consensus public key, node ID, and public P2P endpoint.

## Required guide

- [Live Mainnet validator onboarding](MAINNET_VALIDATOR_ONBOARDING.md)
- [Existing operator preparation kit](STAGE_THREE_OPERATOR_KIT.md)
- [P2P/RPC connectivity and security](testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

## Before a candidate creates a validator

The coordinator must provide the exact binary release and checksum matching the live NodeSafe build, current genesis and checksum, verified P2P seed/peer endpoint, tested create-validator command, actual minimum self-delegation, and Cosmos gas/fee policy.

Until those are published and tested, candidates may qualify their hosts and synchronize a non-validator node, but must not submit a staking transaction based on guessed values. Never use `gentx` or `collect-gentxs` to join the already-running Mainnet.

## Application

Applicants should provide only public operational details:
- Operator/team name and contact method
- Country or broad hosting region
- Hosting provider (no account identifiers)
- Linux distribution/version
- CPU / RAM / SSD
- Expected uptime and maintenance window
- Whether inbound P2P TCP is available
- Cosmos SDK / CometBFT experience
- Preferred role: validator / seed / RPC / full node

No passwords, API keys, mnemonics, private keys, keyring archives, or signing-key files.
