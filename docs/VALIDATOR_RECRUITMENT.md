# SOBYA Independent Validator Recruitment

**Status: expressions of interest may be invited; the SOBYA mainnet is not live yet.**

SOBYA is preparing its public mainnet launch, operated by independent validators. The project does not require a founder-owned validator host. Each participating operator controls and maintains their own Linux host and keeps their own signing keys.

## Recruitment target

The initial target is four independent validator operators, plus one non-validator RPC/full-node operator. A separate seed node is useful. Operators should be distributed across providers/networks where practical.

Operators should be able to provide:
- Persistent Linux infrastructure and reliable power/network.
- Public inbound TCP P2P connectivity (normally port 26656).
- SSD capacity, time synchronization, monitoring, backups, and routine maintenance.
- Experience with Linux operations; Cosmos SDK / CometBFT experience is preferred.

The operator pays for and controls their own infrastructure. No reimbursement, financial return, token price, or guaranteed reward is promised. Validator distributions follow the protocol reserve and signing-eligibility rules; no fiat return, market price, liquidity, exchange listing, or infrastructure reimbursement is promised.

## Safe participation

Each operator creates account, node, and private-validator keys locally. Never send mnemonic phrases, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json` to the project. During the official genesis ceremony, only public account information, node ID, public P2P endpoint, and signed gentx material are exchanged.

## What can be done now

Interested operators may submit an expression of interest using the public application template in [the recruitment publication pack](ANNOUNCEMENTS.md). Host preparation and questions are welcome. Do not create production gentxs or start nodes until the official versioned launch bundle is published.

The launch bundle must include the exact source commit and binary checksums, approved CometBFT and EVM chain IDs, final genesis and SHA-256, tested self-bond/gentx procedure, peer list, gas policy, launch UTC time, and support/incident contact.

## Required reading

- [Complete operator onboarding kit](STAGE_THREE_OPERATOR_KIT.md)
- [Genesis ceremony](GENESIS_CEREMONY.md)
- [Release process](RELEASE_PROCESS.md)
- [Ready-to-publish X and Telegram messages](ANNOUNCEMENTS.md)
- [P2P/RPC security and connectivity](testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

## Mainnet activation gate

The SOBYA mainnet may be described as live only after independent hosts connect over public P2P, report the same chain ID and advancing height, commit blocks, and complete cross-node transactions. Public RPC/EVM endpoints require separate external health and security checks. No placeholder IDs, peer addresses, genesis files, or RPC URLs may be presented as live.
