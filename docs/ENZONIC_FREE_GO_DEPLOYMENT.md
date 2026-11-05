# SOBYA on Enzonic Free Go Hosting — Deployment Preparation

Status: preparation only. The SOBYA-TEST server is still queued; this document does not claim that a node or public testnet is running.

## Confirmed hosting details

The Enzonic support response for ticket #242 stated:

- Free Go application servers do not sleep because of inactivity. The idle-sleep notice on the queue page applies to Minecraft servers.
- Inbound raw TCP is supported.
- A free server receives one provider-assigned inbound TCP port. The operator cannot choose port 26656.
- The public endpoint uses an Enzonic hostname and a mapped port. The public IP is shared.
- The free tier does not provide an additional port for a public RPC endpoint.
- The stated free server resources for this request were 512 MB RAM and 1 GB disk.
- The server's files persist across ordinary stop/restart operations.
- An account with no login for 30 days may receive a warning before server removal; log in periodically.

These details are based on the support response and must be rechecked if the provider changes its free-tier policy.

## Required CometBFT settings after provisioning

Do not fill these values with guesses. Obtain the actual hostname and assigned port from the created server panel first.

In the generated `config/config.toml`:

```toml
[p2p]
laddr = "tcp://0.0.0.0:<ASSIGNED_PORT>"
external_address = "<ENZONIC_PUBLIC_HOSTNAME>:<ASSIGNED_PORT>"

[rpc]
laddr = "tcp://127.0.0.1:26657"
```

- `p2p.laddr` must listen on all interfaces using the provider-assigned port.
- `p2p.external_address` must advertise the externally reachable Enzonic hostname and the same mapped port.
- Keep RPC bound to localhost. The free tier's single inbound port is reserved for P2P; do not expose RPC publicly on an assumed second port.
- Do not hard-code 26656 as the public P2P port.
- Confirm that the assigned port remains unchanged after a restart before publishing it to peer operators.

CometBFT documents `laddr` as the P2P listening address and `external_address` as the address advertised to peers. See https://github.com/cometbft/cometbft/blob/main/docs/core/configuration.md.

## Checks still required from Enzonic

Before launching the chain, confirm both points with support or a real test:

1. Is outbound TCP unrestricted enough for the node to establish connections to other CometBFT peers?
2. Does the assigned inbound TCP port and public hostname remain stable after a stop/start or restart?

Do not assume either answer.

## SOBYA launch gates

The node must not be started as a public validator until the coordinator has agreed and tested:

1. A unique testnet chain ID.
2. Initial token allocation, validator self-delegation, minimum gas price, and transaction fee policy, all denominated in `usobya`.
3. The first validator's key generated locally on the actual validator host.
4. A reproducible genesis file that includes the correct validator public key and allocation.
5. A secure backup procedure for the node home and validator signing key.

Never commit a mnemonic, wallet keyring, `priv_validator_key.json`, `node_key.json`, or live genesis containing private material to GitHub. Never copy one validator's private signing key to another node.

The second validator must have its own independently generated key and separate node home. It must join using the exact same reviewed genesis and chain ID. Do not clone the first validator's data directory or signing key.

## Free-tier suitability

The 512 MB RAM and 1 GB disk allocation are suitable only for a constrained initial experiment, not a promise of long-term public-validator capacity. Blockchain databases and logs grow. Monitor disk and memory from the first boot; do not announce a durable public testnet until resource capacity and recovery have been demonstrated.

One inbound port also means this free server cannot simultaneously expose P2P and a public RPC service. Keep RPC local and use a separate, secured access method if remote inspection is needed.

## Current status

- [ ] Enzonic server provisioned (currently queued; not yet available).
- [ ] Assigned hostname and TCP port recorded.
- [ ] Port stability after restart confirmed.
- [ ] Outbound TCP connectivity confirmed.
- [ ] SOBYA Linux binary built and version checked.
- [ ] Chain ID and token/fee parameters approved.
- [ ] First validator key generated on the host and backed up securely.
- [ ] Genesis created, reviewed, checksummed, and backed up.
- [ ] P2P reachable from an independent external host.
- [ ] Independent second node synchronized and transfer tested.

A successful GitHub Actions localnet workflow is not proof of a public Internet testnet.
