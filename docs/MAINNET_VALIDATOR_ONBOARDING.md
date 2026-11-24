# SOBYA Mainnet — Existing-Network Validator Onboarding

**Purpose:** add independent validators to the already-running SOBYA Mainnet. This is an in-place join procedure, not a genesis ceremony.

## Network identity (confirmed project values)

| Setting | Value |
|---|---|
| CometBFT chain ID | `sobya-1` |
| EVM chain ID (decimal) | `357812033857` |
| EVM chain ID (hex) | `0x534f425941` |
| Native display symbol | `SOBY` |
| Staking / base denomination | `asobya` |
| Display precision | 18 decimals |
| Public CometBFT RPC | `https://sobya-rpc.nodesafe-app.xyz` |
| Public EVM RPC | `https://sobya-evm-rpc.nodesafe-app.xyz` |
| Public REST API | `https://sobya-api.nodesafe-app.xyz` |
| Explorer | `https://explorer.nodesafe-app.xyz/sobya` |

One SOBY equals 1,000,000,000,000,000,000 asobya. The EVM chain ID is not the CometBFT `--chain-id`.

## Important: what is and is not free

- The project will **not send validator grants or transfer SOBY to applicants** as part of ordinary onboarding.
- Applicants provide and pay for their own persistent Linux server, storage, bandwidth, monitoring, and maintenance.
- A validator must make an initial self-delegation. The live API previously reported NodeSafe's `min_self_delegation` as `1`, but this is a per-validator field, not proof that every new validator will be accepted with exactly 1 asobya. Do not advertise a confirmed minimum until a create-validator transaction has been simulated or successfully tested against this live chain.
- EVM gas-price responses of zero do not prove Cosmos SDK staking transactions are fee-free. Confirm the chain's Cosmos minimum gas price and test transaction simulation before promising zero fees.
- If the chain accepts `1 asobya` as the new validator's self-delegation and accepts the transaction with zero fee, the applicant would not need a meaningful SOBY balance and the project would not need to fund them. This is a target to verify, not a guarantee.
- Validator-reserve rewards are protocol rewards subject to the on-chain schedule and eligibility rules; they are not an upfront grant, guaranteed income, or reimbursement for server costs.

## Live-network joining flow

A running Mainnet validator is created with the staking `create-validator` transaction. Do **not** use `gentx`, `collect-gentxs`, a new genesis, or `sobyad init` on an existing node data directory.

1. **Operator qualification.** Confirm a persistent Linux host, SSD, stable connectivity, public inbound P2P TCP (normally 26656), operational contact, and ability to maintain the node. Prefer independent providers and networks.
2. **Release pinning.** The operator must install the exact `sobyad` build approved for the live chain. Verify the binary SHA-256 and `sobyad version` against the coordinator's signed/published release manifest. Never use a mutable branch build or a prerelease merely because its version number looks newer.
3. **Existing-chain configuration.** Use chain ID `sobya-1`, the current live genesis and its verified SHA-256, and coordinator-confirmed seed/persistent-peer information. Do not create a replacement genesis or reset an existing database.
4. **Node synchronization.** Start as a non-validator full node first. Confirm it is fully synchronized with the public chain, has healthy peers, and follows advancing blocks before creating validator keys or submitting staking transactions.
5. **Local keys.** Generate the operator account key and CometBFT consensus key on the operator's own host. The operator retains all mnemonics, keyrings, node keys, and validator signing keys. The project must never request them.
6. **Self-delegation and registration.** After the minimum self-delegation and Cosmos fee policy are confirmed, the operator submits `sobyad tx staking create-validator` with their own account, consensus public key, moniker, commission settings, `asobya` self-delegation, and `min-self-delegation`. The exact command and JSON must be generated from the approved live binary's CLI help and tested on a disposable localnet before publication.
7. **Acceptance.** Query the REST validators endpoint and confirm the new operator address is present, not jailed, and has the expected status. Registration alone does not guarantee `BOND_STATUS_BONDED`: the validator must qualify for the active set under the live staking rules and available voting power.
8. **Operations.** Monitor uptime, peer count, block signing, missed blocks, disk, memory, and clock drift. Keep signing keys private and never run the same consensus key on two machines.

## Commands for public read-only preflight

These checks do not create a validator and do not alter chain state:

```bash
curl -fsS https://sobya-rpc.nodesafe-app.xyz/status
curl -fsS https://sobya-rpc.nodesafe-app.xyz/net_info
curl -fsS https://sobya-api.nodesafe-app.xyz/cosmos/staking/v1beta1/params
curl -fsS https://sobya-api.nodesafe-app.xyz/cosmos/staking/v1beta1/validators
```

The operator must compare the CometBFT network field to `sobya-1`, confirm the height is advancing, and confirm the REST staking denomination is `asobya`. Do not infer a peer address from the HTTPS RPC hostname: the P2P endpoint is a separate service and must be explicitly supplied and externally tested.

## Security rules

- Never share a mnemonic, private key, keyring directory, `priv_validator_key.json`, or `node_key.json`.
- Do not expose CometBFT RPC 26657, EVM RPC 8545/8546, REST 1317, or gRPC 9090 directly to the public internet. Keep backend listeners on loopback and use a hardened authenticated TLS proxy only for services intentionally offered publicly.
- Expose only the P2P port required for peer connectivity.
- Never run `init`, replace genesis, run `gentx`, run `collect-gentxs`, reset the database, or copy another validator's consensus key when joining the live chain.
- Do not send SOBY from founder, treasury, liquidity, emergency, or validator-reserve wallets to make an applicant eligible.

## Publication gate — outstanding values that must be filled from live evidence

This guide intentionally does not invent operational values. Before sending it as a copy-and-run installation recipe, the coordinator must publish and verify all of the following:

1. Exact live binary version, source commit, public release asset URL, and SHA-256. Reconcile the deployed NodeSafe build with the repository release candidate; do not assume a Git branch is a downloadable release.
2. Current genesis download source and SHA-256, verified against the running chain.
3. At least one real, externally reachable P2P seed/persistent-peer endpoint and peer ID; verify from an independent network.
4. Exact minimum self-delegation accepted for a new validator, confirmed by simulation or a successful controlled transaction.
5. Cosmos SDK minimum gas price, fee denomination, and a tested fee/simulation command. EVM `eth_gasPrice` is not a substitute for this check.
6. Exact `create-validator` JSON schema and command flags from the approved binary.
7. A test proving the candidate can register without a project-funded transfer. Any nonzero self-bond or fee must be disclosed before the operator commits.

Until those checks pass, applicants may complete host qualification and synchronize a non-validator node, but must not be told that validator registration is zero-cost or given guessed peer, genesis, binary, or staking values.

## Application details (public information only)

Ask each applicant for: operator/team name, contact method, broad hosting region, provider, Linux distribution, CPU/RAM/SSD, expected uptime, P2P reachability, Cosmos SDK experience, and preferred role. Never request credentials or secrets.

## Project safety boundary

This document is operational guidance only. It does not change chain code, Genesis, staking parameters, validator reserve, fee routing, NodeSafe's running service, or any wallet. Every on-chain action remains under the operator's own signature and explicit approval.
