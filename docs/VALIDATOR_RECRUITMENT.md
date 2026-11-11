# SOBYA Independent Validator Recruitment

**Status: SOBYA mainnet is live on `sobya-1`; independent validator onboarding is open for expressions of interest, while the public P2P/State Sync gate is being resolved.**

SOBYA is expanding from its initial NodeSafe-operated validator to independent validators. Each participating operator controls and maintains their own Linux host and keeps their own signing keys.

## Recruitment target

The initial target is four independent validator operators, plus one non-validator RPC/full-node operator. A separate seed node is useful. Operators should be distributed across providers/networks where practical.

Operators should be able to provide:
- Persistent Linux infrastructure and reliable power/network.
- Public inbound TCP P2P connectivity (normally port 26656; use only the verified project endpoint/port when published).
- SSD capacity, time synchronization, monitoring, backups, and routine maintenance.
- Experience with Linux operations; Cosmos SDK / CometBFT experience is preferred.

The operator pays for and controls their own infrastructure. No reimbursement, financial return, token price, or guaranteed reward is promised. Validator distributions follow the protocol reserve and signing-eligibility rules; no fiat return, market price, liquidity, exchange listing, or infrastructure reimbursement is promised.

## Safe participation

Each operator creates account, node, and private-validator keys locally. Never send mnemonic phrases, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json` to the project. Operators share only public account information, node ID, public P2P endpoint, and other explicitly requested public onboarding details.

## What can be done now

Interested operators may submit an expression of interest using the public [validator application template](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml). Host preparation and questions are welcome.

**Do not create production gentxs or broadcast `create-validator` transactions yet.** The external preflight on 2026-11-11 verified the public CometBFT RPC, Cosmos REST, and EVM JSON-RPC endpoints, but the previously supplied P2P endpoint `188.68.36.11:36656` timed out from an external runner and CometBFT reported zero connected peers. The team must obtain a reachable P2P/seed endpoint or a verified State Sync procedure, then publish the exact supported binary/checksum, live Genesis checksum, and current staking/self-delegation/fee parameters.

## Required reading

- [Validator onboarding and live preflight status](validator-support/ONBOARDING.md)
- [Genesis ceremony](GENESIS_CEREMONY.md)
- [Release process](RELEASE_PROCESS.md)
- [P2P/RPC security and connectivity](testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

## Mainnet operation

SOBYA mainnet is live. A public RPC endpoint is not a substitute for P2P connectivity or a State Sync procedure. New operators must independently synchronize to the live chain, verify chain ID and height, and only then create their own validator using the approved live-chain procedure. Do not generate a new genesis gentx for the already-running network.
