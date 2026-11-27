# SOBYA Mainnet — P2P and RPC operations reference

**SOBYA Mainnet is live.** This document is the operational security and connectivity reference for nodes joining or serving the existing network. It is not a launch-readiness gate.

## Production network identity and endpoints

- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- CometBFT RPC: `https://sobya-rpc.nodesafe-dapp.xyz`
- REST API: `https://sobya-api.nodesafe-dapp.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

Use EVM JSON-RPC for MetaMask and EVM applications. CometBFT RPC is for consensus/node queries. REST is a separate Cosmos API.

## Network roles and exposure

| Role | Purpose | Recommended public inbound access |
|---|---|---|
| Validator | Consensus, block signing and P2P | P2P only (normally TCP 26656 or provider-mapped port) |
| Seed node | Peer discovery; no validator signing key | P2P only |
| RPC/full node | Non-validator sync node and public query backend | P2P as needed and HTTPS reverse proxy (normally 443) |

Keep CometBFT administrative RPC on loopback. For designated RPC nodes, keep EVM JSON-RPC and WebSocket backends on loopback behind a hardened TLS reverse proxy. Expose only required read-only namespaces. Do not enable insecure account unlocking, profiling, personal/debug/miner namespaces, or unsafe CometBFT RPC.

## Joining the live chain

Use the currently supported release and the existing network's verified genesis and peer information. Configure CometBFT chain ID `sobya-1` and EVM chain ID `357812033857`. Synchronize to the existing network and confirm the chain ID and advancing height before creating a validator.

Do not create a new genesis or submit a genesis gentx to join the live network. A joining validator uses the supported live-chain staking transaction and the current on-chain self-delegation and fee requirements.

## Configuration guidance

- Keep `config/client.toml` chain ID consistent with the existing network's `sobya-1`.
- CometBFT P2P should advertise the operator's real externally reachable host and port.
- Keep CometBFT RPC bound to `127.0.0.1:26657`; disable unsafe RPC.
- Keep EVM JSON-RPC bound to `127.0.0.1:8545` and WebSocket to `127.0.0.1:8546` on a designated RPC node, then expose through a secured reverse proxy.
- Use the production EVM chain ID `357812033857`.
- Apply the current minimum gas price and other operational parameters confirmed from the live chain and supported release; do not copy stale sample values blindly.

The local configuration audit remains useful for validating a node home. Its test fixtures and local networks are not the production network.

## Development-only identifiers

EVM chain IDs `777777` and `777778`, and historical identifiers such as `sobya-testnet-stage2`, are reserved for local development or CI. They are not SOBYA Mainnet identifiers.

## Firewall and host security

- Validator/seed: allow inbound TCP only on the actual P2P port; allow outbound connections to peers. Do not expose 26657, 8545, 8546, 1317 or 9090 directly.
- RPC/full node: expose HTTPS through a hardened reverse proxy; keep backend RPC listeners on loopback.
- Restrict SSH to the operator's administration IPs.
- Use host firewall rules, automatic security updates, time synchronization, log rotation, disk alerts, monitoring and protected backups.
- Verify provider-mapped ports from a second network after restart.
- Do not rely on an experimental relay or one provider as the sole production peer path.

## CI and test environments

Localnet, multi-validator and EVM smoke tests are regression tests. GitHub Actions runners are temporary and do not host the live chain. A test workflow passing or failing does not change the operational state of SOBYA Mainnet.
