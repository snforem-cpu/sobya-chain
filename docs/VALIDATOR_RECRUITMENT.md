# SOBYA Independent Validator Recruitment

**Status: SOBYA mainnet is live on `sobya-1`; independent validator onboarding is open for expressions of interest.**

SOBYA is expanding from its initial NodeSafe-operated validator to independent validators. Each participating operator controls and maintains their own Linux host and keeps their own signing keys.

## Recruitment target

The initial target is four independent validator operators, plus one non-validator RPC/full-node operator. A separate seed node is useful. Operators should be distributed across providers/networks where practical.

Operators should be able to provide:
- Persistent Linux infrastructure and reliable power/network.
- Public inbound TCP P2P connectivity (normally port 26656; use the verified project peer below for initial synchronization).
- SSD capacity, time synchronization, monitoring, backups, and routine maintenance.
- Experience with Linux operations; Cosmos SDK / CometBFT experience is preferred.

The operator pays for and controls their own infrastructure. No reimbursement, financial return, token price, or guaranteed reward is promised. Validator distributions follow the protocol reserve and signing-eligibility rules; no fiat return, market price, liquidity, exchange listing, or infrastructure reimbursement is promised.

## Safe participation

Each operator creates account, node, and private-validator keys locally. Never send mnemonic phrases, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json` to the project. Operators share only public account information, node ID, public P2P endpoint, and other explicitly requested public onboarding details.

## What can be done now

Interested operators may submit an expression of interest using the public [validator application template](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml). Host preparation and questions are welcome.

The external preflight on 2026-11-11 verified the public CometBFT RPC, Cosmos REST, EVM JSON-RPC, and TCP reachability of NodeSafe's CometBFT P2P port 26656. The peer endpoint is `1dad50ff897c247cba0ff646d0ee1ad59c3abc88@188.68.36.11:26656`. A second independent node has not yet completed a P2P handshake and block sync.

**Do not create production gentxs or broadcast `create-validator` transactions yet.** The team must obtain the exact live mainnet Genesis and SHA-256, confirm the running binary/version, and publish current staking/self-delegation/fee parameters. The repository's older BonyNode rehearsal Genesis is not the live NodeSafe mainnet Genesis and must not be used for onboarding.

## Required reading

- [Validator onboarding and live preflight status](validator-support/ONBOARDING.md)
- [Genesis ceremony](GENESIS_CEREMONY.md)
- [Release process](RELEASE_PROCESS.md)
- [P2P/RPC security and connectivity](testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

## Mainnet operation

SOBYA mainnet is live. Public RPC helps operators inspect the chain, while P2P provides peer connectivity and block synchronization. New operators must independently synchronize to the live chain, verify chain ID and height, and only then create their own validator using the approved live-chain procedure. Do not generate a new genesis gentx for the already-running network.
