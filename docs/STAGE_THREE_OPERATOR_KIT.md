# SOBYA — Independent Operator Onboarding Kit

**Status: preparation / recruitment. This is not a live testnet or mainnet.** This kit is for operators who want to volunteer an independently controlled host. Do not start a node on a guessed chain ID or draft genesis.

## 1. Roles and minimum topology

- **Validator:** runs SOBYA continuously, signs consensus blocks, exposes P2P only. The operator owns and protects the validator signing key.
- **Seed:** helps peers discover one another; no validator signing key is required.
- **RPC/full node:** non-validator node that may offer read access through a hardened HTTPS reverse proxy. It must not expose backend RPC ports directly.

Target the initial public testnet at four independent validator operators, plus one non-validator RPC/full-node operator. A seed operator is helpful but may be one of the volunteers if roles are separated carefully. Operators should use different providers/networks where practical. This is a recruitment target, not a claim that operators already exist.

Each operator supplies their own persistent Linux host, stable power/network, SSD, public inbound P2P reachability (normally TCP 26656), time synchronization, monitoring, backups, and maintenance. No founder-owned host is a prerequisite.

## 2. Before installing

Wait for the coordinator to publish a **versioned launch bundle** containing all of:
- SOBYA source commit and version/tag.
- Tested binary download and SHA-256 checksum, or exact reproducible build instructions.
- Official CometBFT chain ID and unique EVM chain ID (not development/CI IDs 777777 or 777778).
- Final genesis file and SHA-256 checksum.
- Exact self-bond amount, tested gentx command, minimum gas price, P2P peers/seeds, launch UTC time.
- Support and incident-reporting channel.

Until that bundle is published, operators may prepare hosts and express interest, but must not create production keys for a live network, sign a gentx, or start a public node using placeholders.

## 3. Host preparation and installation

Use a currently supported Linux distribution on a machine you control. Apply security updates, configure a firewall, synchronize the clock, enable log rotation, and ensure the service can restart after reboot. Keep adequate free SSD space and monitor disk/inode use.

Install only the binary from the official versioned release and verify it first:

```bash
sha256sum -c SHA256SUMS
./sobyad version
```

The release checksum file must be downloaded from the same official release page as the binary. Do not run an unverified binary.

## 4. Create local node and account keys

Use the official chain ID from the launch bundle. Example command shape (replace only with published values):

```bash
export SOBYA_HOME="$HOME/.sobya"
install -d -m 700 "$SOBYA_HOME"
./sobyad init "YOUR_MONIKER" --chain-id "<OFFICIAL_COMETBFT_CHAIN_ID>" --home "$SOBYA_HOME"
./sobyad keys add validator --keyring-backend os --home "$SOBYA_HOME"
./sobyad tendermint show-node-id --home "$SOBYA_HOME"
```

Record your public account address and node ID locally. Never send the mnemonic, keyring directory, node key, or private-validator signing key to the coordinator. Back up secrets offline using your own secure process. Do not run the same validator signing key on two machines.

## 5. Genesis contribution (only when requested)

The coordinator will publish the exact tested command and self-bond amount. Create the gentx locally with your own keyring, then submit only:
- Signed gentx JSON file.
- Public account address and moniker.
- Node ID and public P2P endpoint.
- Operator contact and broad hosting region.

A gentx is public signed genesis material; it is not a private key. Inspect it before submission and ensure it contains no secret material. Do not send a wallet export, mnemonic, private key, keyring, `priv_validator_key.json`, or `node_key.json`.

## 6. Configure peers and node services

Use only real peer values distributed in the launch bundle. Do not copy another operator's node key. For validator and seed nodes:
- P2P listener: externally reachable TCP port (normally 26656).
- Advertise the real public DNS/IP and externally reachable port.
- CometBFT RPC: loopback only; unsafe RPC disabled.
- EVM JSON-RPC: disabled on validator and seed nodes.
- Do not expose 26657, 8545, 8546, REST 1317, or gRPC 9090 directly.

For a designated RPC node, enable only the required read-only EVM namespaces and keep backend listeners on loopback behind TLS, authentication/rate limits as appropriate, and a hardened reverse proxy. Never enable insecure account unlock, profiling, or personal/debug/miner namespaces.

Run the repository configuration audit against the actual generated files and the exact launch-bundle IDs:

```bash
python3 scripts/validate-network-config.py \
  --config "$SOBYA_HOME/config/config.toml" \
  --app-config "$SOBYA_HOME/config/app.toml" \
  --genesis "$SOBYA_HOME/config/genesis.json" \
  --chain-id "<OFFICIAL_COMETBFT_CHAIN_ID>" \
  --evm-chain-id "<OFFICIAL_EVM_CHAIN_ID>" \
  --role validator
```

Use `--role seed` or `--role rpc` for those roles. This is a local configuration audit, not proof of public reachability.

## 7. Start, sync, and monitor

Start only at the coordinated UTC launch time, after independently verifying the final genesis checksum:

```bash
sha256sum "$SOBYA_HOME/config/genesis.json"
./sobyad start --home "$SOBYA_HOME"
```

Monitor process health, disk space, memory, peer count, latest height, missed blocks, logs, and clock drift. Confirm the node follows the same chain ID and advancing height as other independent operators. Report incidents promptly; do not delete or replace validator state casually.

## 8. Backups, upgrades, and recovery

- Keep encrypted offline backups of account/key material under your own custody.
- Protect validator signing state; coordinate recovery to avoid double-signing.
- Back up configuration and genesis separately from secrets.
- Test restore procedures on a non-validator copy before relying on them.
- Upgrade only to coordinator-approved versions at the announced height/time.
- Never restore an old validator signing state over a newer state without a documented recovery procedure.

## 9. Public connectivity acceptance

After at least two independent hosts are running, test P2P from a third network. Verify peer IDs, common CometBFT chain ID, synchronized heights, block commits, and cross-node transactions. The coordinator's external probe is documented in `docs/testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md`. Publish RPC endpoints only after external health and security checks.

## 10. Operator application

Submit public operational details only:
- Operator/team name and contact:
- Country or broad hosting region:
- Provider (no account identifiers or credentials):
- Linux distribution/version:
- CPU / RAM / SSD:
- Expected uptime and maintenance window:
- Can you expose inbound P2P TCP? yes/no:
- Experience with Cosmos SDK / CometBFT:
- Preferred role: validator / seed / RPC / full node:

Do not include passwords, API keys, mnemonics, private keys, keyring archives, or signing-key files.

## 11. Token and reward disclosures

SOBY uses base denomination `asobya`, 18 decimals, and a planned 1,000,000,000 SOBY native supply cap. The agreed allocation and fee policy are documented in `sobya/TOKENOMICS.md`. The validator reserve is a protocol-controlled allocation with a 48-period schedule and a 95% signing eligibility rule; it is not a guaranteed income. Testnet tokens have no monetary value. Operators pay for and control their own infrastructure; no reimbursement, profit, exchange listing, or token price is promised.

**Never run a production validator until the official release, chain IDs, final genesis, checksum, peers, and launch time have been published.**
