# SOBYA Testnet Validator Operator Guide

This guide is for independent operators joining the **public testnet after the coordinator publishes the final genesis**. Do not start a validator on an unofficial or incomplete genesis.

## 1. Prepare your validator home

Use the exact approved SOBYA binary/source release and the CometBFT chain ID announced by the coordinator (proposed: `sobya-testnet-1`).

```bash
sobyad init "YOUR_MONIKER" --chain-id sobya-testnet-1
```

Create your own account key locally. Use a secure local keyring backend; never send its contents to the coordinator.

```bash
sobyad keys add validator --keyring-backend os
```

Keep the generated home directory, especially:

- `config/priv_validator_key.json`
- `config/node_key.json`
- Your local keyring

These files are private. Do not upload them, paste them into chat, or send them to the coordinator.

## 2. Create and send only your gentx

The coordinator will announce the exact self-bond amount before the genesis ceremony. The following is an example only; do not choose a different amount without coordinating it.

```bash
sobyad gentx validator 100000000000000000000asobya \
  --chain-id sobya-testnet-1 \
  --keyring-backend os \
  --commission-rate 0.10 \
  --commission-max-rate 1.00 \
  --commission-max-change-rate 0.10 \
  --min-self-delegation 1
```

Send the resulting signed `config/gentx/gentx-*.json` file to the coordinator, plus your public account address, validator moniker, public IP/DNS name, and node ID.

To display your node ID:

```bash
sobyad tendermint show-node-id --home ~/.sobya
```

The gentx is public genesis material. It is not a private key. Never send your keyring, mnemonic, node key, or private-validator key.

## 3. Wait for the final genesis ceremony

The coordinator will:

- Validate the gentx set and validator self-bonds.
- Account for those self-bonds inside the 150M SOBY validator allocation.
- Add the founder/shared-wallet allocations and fund the validator reserve module account with the remaining validator allocation.
- Freeze the CometBFT chain ID and one unique EVM chain ID.
- Publish the final genesis file and its SHA-256 hash.

Do not start until you have received the final genesis file, the exact SHA-256 hash, and the approved peer list.

Verify the genesis file before replacing your local copy:

```bash
sha256sum genesis.json
```

The result must exactly match the coordinator's published hash. Copy the approved file to `~/.sobya/config/genesis.json`, preserving your original `priv_validator_key.json`, `node_key.json`, and keyring.

## 4. Set the shared EVM chain ID and peers

Every operator must use the same EVM chain ID. In `~/.sobya/config/app.toml`, under the `[evm]` section, set:

```toml
evm-chain-id = <COORDINATOR_PUBLISHED_EVM_CHAIN_ID>
```

Do not use the development/CI default `777777` for the public testnet.

In `~/.sobya/config/config.toml`, set the coordinator-provided `persistent_peers` and your public `external_address`. Keep the P2P port reachable (normally TCP 26656).

Do not invent peer IDs or addresses. Use only the values published by the coordinator.

## 5. Start and verify

After the coordinator announces the network start time:

```bash
sobyad start --home ~/.sobya
```

Check that the node is catching up and then following the same latest height as the other validators:

```bash
sobyad status --node tcp://127.0.0.1:26657
sobyad query staking validators --node tcp://127.0.0.1:26657
```

Keep the process supervised, retain persistent storage, monitor disk space and logs, and report downtime to the coordinator.

## 6. Network safety

- Never share private-validator keys, keyrings, seed phrases, or signing keys.
- Never run two live nodes with the same validator private key.
- Do not expose the node's unsafe/admin RPC methods.
- Expose P2P only as required; put public RPC/EVM endpoints behind a hardened TLS proxy with rate limits.
- Do not use testnet SOBY as an asset with promised monetary value. Testnet tokens are for testing only.
- Do not reuse testnet keys or genesis files for mainnet.
