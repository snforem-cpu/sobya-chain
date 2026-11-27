# SOBYA — Independent Validator and Node Operator Guide

**SOBYA Mainnet is live.** This guide is for operators joining the existing production network. It is not a genesis ceremony or testnet launch checklist.

## Production network identity

- Network: `SOBYA Mainnet`
- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`
- Native asset: `SOBY`
- Base denomination: `asobya` (18 decimals)

Public endpoints:
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- CometBFT RPC: `https://sobya-rpc.nodesafe-dapp.xyz`
- REST API: `https://sobya-api.nodesafe-dapp.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

Use the EVM endpoint for MetaMask and EVM applications. Use CometBFT RPC for consensus/node queries. These endpoints are different protocols.

## Operator roles

- **Validator:** operates a node, signs consensus blocks and participates in network consensus.
- **RPC/full node:** synchronizes with the live chain and provides read access through secured endpoints.
- **Seed/peer:** supports peer discovery and P2P connectivity.

Operators should use infrastructure they control, maintain reliable connectivity, protect signing keys, monitor disk and process health, and keep secure backups. Independent providers and network paths improve resilience.

## Join the existing network

1. Contact the SOBYA team through the official project channels and confirm the currently supported release and checksum.
2. Install the approved binary on a Linux host you control.
3. Configure CometBFT chain ID `sobya-1` and EVM chain ID `357812033857`.
4. Obtain current peer/bootstrap information from the project. Do not use stale or guessed peer IDs.
5. Synchronize from the existing network and confirm that the node reports `sobya-1` and an advancing block height.
6. Confirm current staking parameters, minimum self-delegation, denomination and transaction fees from the live chain.
7. Create a validator using the supported live-chain transaction flow. The operator signs the transaction with their own wallet.

**Do not run `genesis gentx`, create a new genesis file, or start a separate chain to join SOBYA Mainnet.** Those steps belong only to a new network ceremony and are not used for an already-running chain.

## Secure key handling

Generate account, node and validator keys locally. Keep `priv_validator_key.json`, `node_key.json`, keyring files, mnemonics and private keys under the operator's control. Never send them to the project or publish them in GitHub Issues, chat, logs or CI artifacts. Never run the same validator signing key on two machines simultaneously.

## Node exposure policy

- Keep CometBFT administrative RPC bound to loopback unless it is exposed through a hardened, read-only reverse proxy.
- Keep EVM JSON-RPC and WebSocket backends on loopback behind a secured reverse proxy on operator-managed RPC nodes.
- Do not enable insecure account unlocking, profiling, or personal/debug/miner namespaces.
- Expose P2P only as required for peer connectivity.
- Apply firewall rules, rate limits, TLS, monitoring, log rotation, time synchronization and protected backups.

## Development and CI identifiers

The local development/CI EVM identifiers `777777` and `777778` are not production network IDs. CI runners are temporary test environments, not validator hosts. Do not use local testnet instructions to join the live network.

## Support and rewards

Validator participation is governed by live on-chain staking parameters and the protocol's validator-reserve eligibility rules. No fiat income, market price, liquidity, exchange listing or infrastructure reimbursement is guaranteed.
