# SOBYA Independent Validator Recruitment Pack

> Status: recruitment preparation only. This document is not a public-network launch notice. No live RPC endpoint, peer address, final genesis hash, or public chain ID is published here.

## Why independent validators are needed

SOBYA is intended to run continuously through independently operated nodes rather than a single founder-funded server. Each validator supplies and maintains its own always-on Linux host, stores its own signing keys, peers with the other operators, and participates in CometBFT consensus. GitHub Actions is used for builds and tests only; it is not validator hosting.

A public testnet should not start until at least four independent operators have confirmed their ability to keep nodes online. Operators should be in different hosting providers or networks where practical. A separate non-validator full node should provide public RPC access; a separate seed/peer node is desirable.

## What an operator contributes

- A Linux server or dedicated machine under the operator's control, intended to run 24/7.
- Stable public connectivity and inbound TCP P2P access (normally port 26656).
- Persistent SSD storage, reliable power/network, system clock synchronization, and enough capacity for chain growth.
- Routine process supervision, disk/log monitoring, secure backups, and timely upgrades.
- Their own validator account and private-validator signing key, generated and kept locally.

The operator pays for and controls their own infrastructure. SOBYA does not promise reimbursement, income, token value, or guaranteed validator rewards. Testnet tokens have no monetary value.

## Operator safety rules

1. Generate account keys, node keys, and private-validator keys locally on the operator's own host.
2. Never send a mnemonic, private key, keyring directory, `priv_validator_key.json`, or `node_key.json` to the project coordinator.
3. Share only public information: operator contact, moniker, public account address, node ID, public P2P address, hosting/network region, and signed genesis transaction when requested.
4. Never run the same validator signing key on two machines at once.
5. Do not expose CometBFT unsafe/admin RPC methods. Public RPC/EVM endpoints must be separately hardened, rate-limited, and protected with TLS/reverse-proxy controls.
6. Do not use testnet keys or assets for real funds.

## What the coordinator must publish before operators start

The coordinator must issue one signed-off launch bundle containing:

- Approved SOBYA source commit and binary version, with SHA-256 checksums.
- Final CometBFT chain ID and a separately finalized, unique EVM chain ID. The development EVM ID `777777` must not be reused by assumption.
- Final genesis JSON and its SHA-256 checksum.
- Initial validator self-bond amount and exact tested gentx commands.
- Approved P2P seed/persistent-peer list and launch time.
- Minimum gas price, public RPC policy, and official support/incident contact.
- A clear statement that this is a testnet and testnet tokens have no monetary value.

All operators must verify the exact same genesis checksum and software version before starting. Do not start from a draft or locally modified genesis.

## Readiness sequence

1. Recruit at least four independent validator operators and one RPC/full-node operator.
2. Confirm that each operator can provide a persistent host and public P2P reachability.
3. Freeze the exact source commit, network IDs, token parameters, and genesis ceremony.
4. Have each operator create their keys locally and submit only public addresses and signed gentx material.
5. Build and validate one genesis, reconcile the entire initial supply to the agreed 1,000,000,000 SOBY cap, and publish its checksum.
6. Have operators verify the checksum, configure the published peers, and start at the coordinated time.
7. Verify from outside each hosting network that independent nodes peer, commit the same heights, and complete cross-node transactions.
8. Publish public RPC/EVM endpoints only after security and health checks. Assign monitoring, backup, upgrade, and incident responsibilities.

## Operator application template

Interested operators can submit the following public information once an official recruitment channel is announced:

- Operator / team name:
- Contact method:
- Country or broad hosting region:
- Hosting provider (do not include account credentials):
- Linux distribution and version:
- CPU / RAM / SSD capacity:
- Expected uptime and maintenance window:
- Public P2P DNS or IP (only when ready):
- Node ID (only after generating it locally):
- Validator account public address (only after generating it locally):
- Experience operating Cosmos SDK / CometBFT nodes:

Do not include passwords, API tokens, mnemonics, private keys, keyring files, or private-validator files.

## Public recruitment notice (draft)

**SOBYA is preparing an independent-validator testnet.**

We are inviting technically capable operators to help run SOBYA nodes on independently controlled Linux servers. The goal is a decentralized test network maintained by multiple operators, not a single centrally hosted node.

Operators should be able to maintain a server online 24/7, allow P2P connectivity, monitor their node, and follow coordinated software/genesis upgrades. Each operator keeps their own keys; the project will never request private keys or seed phrases.

This is a testnet participation opportunity, not an investment offer. Testnet tokens have no monetary value, and no financial return or reimbursement is promised.

**Applications are not open until the official chain IDs, genesis, binary checksums, peer information, and support channel are published.** Until then, this is a preparation notice only.

## Launch status checklist

- [ ] Repository/source release is publicly accessible to prospective operators.
- [ ] Four or more independent validator operators confirmed.
- [ ] One independent RPC/full-node operator confirmed.
- [ ] Final CometBFT and EVM chain IDs approved.
- [ ] Genesis and supply reconciliation completed; final SHA-256 published.
- [ ] Tested binary and checksum published for supported host architectures.
- [ ] Peer list and launch time published.
- [ ] Public RPC/EVM exposure reviewed and hardened.
- [ ] Independent-host consensus and cross-node transfer verified.
- [ ] Monitoring, backups, upgrades, and incident contacts assigned.

A network may be described as a live public testnet only after these operational checks have actually passed.
