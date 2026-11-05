# SOBYA Stage 2 — P2P and RPC network readiness

Status: configuration and validation package prepared. **No public peer, public RPC endpoint, or independently hosted node has been verified yet.** This document is not a launch announcement.

## Scope and exit criteria

Stage 2 prepares and verifies the network connectivity layer:

1. CometBFT P2P listeners advertise a real public address and connect through verified persistent peers or seed nodes.
2. Validator nodes expose only P2P to the public Internet; CometBFT RPC stays on loopback.
3. A separate non-validator RPC/full node serves CometBFT read queries and EVM JSON-RPC behind a TLS reverse proxy.
4. EVM JSON-RPC has restricted namespaces, loopback backend listeners, no insecure account unlocking, no profiling, finite connection limits, and explicit WebSocket origins.
5. Each node's configuration is checked against the exact launch chain IDs and genesis before startup.
6. Independent external probes confirm TCP P2P reachability, peer discovery, shared chain ID/height, CometBFT status, EVM chain ID, and block height.

The first five items can be prepared in the repository. Item 6 requires real public hosts and published peer/RPC addresses; CI cannot prove Internet reachability.

## Network roles

| Role | Purpose | Public inbound ports |
|---|---|---|
| Validator | Consensus, block signing, P2P | TCP P2P only (normally 26656; use provider-mapped port when applicable) |
| Seed node | Peer discovery and connection bootstrapping; no validator signing key | TCP P2P only |
| RPC/full node | Non-validator sync node and public query backend | P2P plus TLS reverse proxy (normally 443); backend RPC remains loopback |

Recommended initial topology: four independent validator operators, one separate RPC/full node, and one seed node if a stable independent host is available. Do not place all roles on one free-tier machine or assume a Cloudflare Worker is a validator.

## CometBFT `config/config.toml`

After generating the node home with the exact approved SOBYA binary, set the following values. Replace every uppercase placeholder using information collected from the actual host and approved launch bundle; never publish a placeholder as a working peer.

Validator/seed P2P settings:

```toml
[p2p]
laddr = "tcp://0.0.0.0:26656"
external_address = "NODE_PUBLIC_DNS_OR_IP:26656"
persistent_peers = "40_HEX_NODE_ID@SEED_PUBLIC_DNS_OR_IP:26656"
seeds = "40_HEX_SEED_NODE_ID@SEED_PUBLIC_DNS_OR_IP:26656"

[rpc]
laddr = "tcp://127.0.0.1:26657"
unsafe = false
```

- On a directly reachable host, advertise the P2P listener port. If a provider maps a public port to a different internal port, advertise the externally reachable mapped port and verify the forwarding from a second network; the config auditor accepts this documented mapping.
- `persistent_peers` should contain known stable peers; `seeds` can help discover additional peers. The values must be real CometBFT node IDs and reachable host/port pairs.
- Never copy `node_key.json` between operators. Each host must generate its own node key.
- Do not open CometBFT RPC port 26657 to the public Internet. Keep unsafe RPC disabled.

## Dedicated RPC/full-node `app.toml`

The RPC node is a non-validator node. Its local services are intended to be reached only by a same-host reverse proxy:

```toml
minimum-gas-prices = "1000000000asobya"

[api]
enable = false

[grpc]
enable = false

[json-rpc]
enable = true
api = ["eth", "net", "web3"]
address = "127.0.0.1:8545"
ws-address = "127.0.0.1:8546"
allow-insecure-unlock = false
enable-profiling = false
max-open-connections = 100
ws-origins = ["127.0.0.1", "localhost"]

[evm]
evm-chain-id = 357812033857 # proposed SOBYA ID; use only after owner approval and final registry check
```

CometBFT RPC remains at `tcp://127.0.0.1:26657` in `config.toml`. Expose the required read-only routes through a TLS reverse proxy on 443, with rate limits and request-size/time limits. Do not expose `personal`, `debug`, or `miner` JSON-RPC namespaces; do not enable insecure account unlocking or profiling. Use an explicit WebSocket origin allowlist for the official wallet/application origins after those domains exist.

The required Cosmos minimum gas price is `1000000000asobya` per gas, matching the default EVM initial base fee; the local configuration audit rejects a different or empty value. Apply it to every validator and RPC node.

The proposed production pair is CometBFT `sobya-1` and EVM `357812033857` (`0x534f425941`, ASCII-derived from SOBYA), subject to owner approval and a final registry check. The EVM candidate was not listed in ethereum-lists/chains on 2026-11-05; this does not reserve it or prove no private chain uses it. The EVM chain IDs `777777` (development default) and `777778` (network-config CI fixture) are reserved for development/testing and must not be used for a public network. Freeze both IDs together with the genesis and launch bundle.

## Firewall policy

- Validator/seed: allow inbound TCP only on the actual P2P port from the Internet; allow outbound TCP to peers. Do not expose 26657, 8545, 8546, 1317, or 9090.
- RPC/full node: allow P2P as required; expose HTTPS 443 through a hardened reverse proxy. Keep 26657, 8545, and 8546 bound to loopback. Keep REST and gRPC disabled unless separately reviewed.
- Restrict SSH to the operator's administration IPs. Use host firewall rules, automatic security updates, time synchronization, log rotation, disk alerts, and protected backups.
- A provider-assigned TCP port must be tested from a second network after restart. Do not assume a port or hostname is stable.
- Do not use the experimental Cloudflare Durable Objects relay as the sole production peer path. It is a two-role transport experiment, not a validator host or public RPC service.

## Configuration audit

Run the included validator against the actual node home and the signed-off launch bundle:

```bash
python3 scripts/validate-network-config.py \
  --config "$HOME/.sobya/config/config.toml" \
  --app-config "$HOME/.sobya/config/app.toml" \
  --genesis "$HOME/.sobya/config/genesis.json" \
  --chain-id "<OFFICIAL_COMETBFT_CHAIN_ID>" \
  --evm-chain-id "<OFFICIAL_EVM_CHAIN_ID>" \
  --role rpc
```

Use `--role validator` for validator hosts and `--role seed` for seed-only hosts; those profiles require EVM JSON-RPC to remain disabled. The initial seed may have no upstream peers, while validator and RPC nodes must list at least one real peer or seed. The `rpc` profile requires EVM JSON-RPC to be enabled but loopback-bound behind the TLS proxy.

The audit rejects missing EVM genesis state, chain-ID mismatches, the development EVM ID, empty peer/seed lists on non-seed nodes, placeholder or private advertised addresses, unsafe RPC, public backend listeners, insecure account unlocking, dangerous JSON-RPC namespaces, wildcard WebSocket origins, and unbounded RPC connections.

This audit validates local files only. It cannot prove that DNS resolves, a firewall is open, a peer accepts connections, or an RPC endpoint is reachable from outside.

## External acceptance checks

Run these from a machine outside the node's hosting provider/network:

```bash
# P2P TCP reachability
nc -vz <PUBLIC_P2P_HOST> <PUBLIC_P2P_PORT>

# CometBFT status through the secured public read endpoint
curl -fsS https://<OFFICIAL_RPC_HOST>/status

# EVM chain ID and latest block through the public TLS endpoint
curl -fsS https://<OFFICIAL_EVM_RPC_HOST> \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

curl -fsS https://<OFFICIAL_EVM_RPC_HOST> \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":2}'
```

Also inspect `/net_info` on the local CometBFT RPC interface and verify that the expected independent peer IDs are connected. Confirm that at least two independently hosted nodes report the same CometBFT chain ID and advancing height, then complete a transaction between separately controlled accounts.

### One-command external probe

After publishing the real endpoints, run the probe from a separate network (for example, another operator's host). Supply only public addresses and identifiers:

```bash
export SOBYA_P2P_HOST="<PUBLIC_P2P_HOST>"
export SOBYA_P2P_PORT="<PUBLIC_P2P_PORT>"
export SOBYA_RPC_URL="https://<OFFICIAL_RPC_HOST>"
export SOBYA_EVM_RPC_URL="https://<OFFICIAL_EVM_RPC_HOST>"
export SOBYA_CHAIN_ID="<OFFICIAL_COMETBFT_CHAIN_ID>"
export SOBYA_EVM_CHAIN_ID="<OFFICIAL_EVM_CHAIN_ID>"
export SOBYA_MIN_PEERS=1
bash scripts/probe-public-network.sh
```

The probe checks public TCP reachability, CometBFT chain ID and block height, connected peer count, EVM chain ID, and EVM block number. It requires `curl`, `jq`, and `nc`. It makes read-only requests and never needs a wallet key or validator secret.

## Current verified state and remaining external dependencies

- [x] SOBYA CI has already exercised two local CometBFT validators and peer connectivity on one temporary runner.
- [x] Default EVM JSON-RPC remains disabled and loopback-bound; insecure account unlocking and profiling are explicitly disabled in the application defaults.
- [x] A strict configuration audit script and CI self-test are included.
- [ ] Real seed/persistent-peer node IDs and public addresses supplied by independent operators.
- [ ] Stable P2P ports and outbound TCP verified from each actual host.
- [ ] Separate non-validator RPC/full-node host provisioned and synchronized.
- [ ] Official chain IDs and final genesis bundle approved; current CI chain IDs are not production identifiers.
- [ ] TLS reverse proxy, DNS, firewall, rate limits, and WebSocket origin allowlist configured.
- [ ] External probes and cross-host peer/height/transaction checks passed.

**Stage 2 is not complete until the external checks above pass.** No public P2P address or RPC URL is currently being asserted as live.
