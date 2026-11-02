# SOBYA Public Testnet Operator Guide (Preparation)

This document is an operational preparation guide, not an announcement that a public testnet is live. A public launch remains blocked until independent operators, public P2P reachability, a reviewed common genesis, and successful cross-node transfers have been verified.

## Current development token parameters

- Display token: `SOBY`.
- Native base denomination: `asobya`.
- Precision: 18 decimals (`1 SOBY = 10^18 asobya`).
- Maximum native supply: 1 billion SOBY.

These are development parameters. The public testnet chain ID, EVM chain ID, genesis time, validator allocations, minimum gas price, and launch date are not yet finalized.

## Before announcing a public testnet

The coordinator and operators must agree on and publish:

1. A unique, stable Cosmos chain ID and EVM chain ID.
2. The genesis time, initial validator set, initial account allocations, and denomination `asobya`.
3. The minimum gas price and transaction fee policy, expressed in the 18-decimal base denomination.
4. At least two independently operated validator or full-node hosts.
5. Public P2P addresses and persistent peer information.
6. A checksum (SHA-256) for the final, shared genesis file.
7. A support/contact channel and a clear statement that testnet tokens have no monetary value.

Do not put mnemonics, private validator keys, keyring directories, or wallet secrets in this repository, CI artifacts, public issue comments, or logs.

## Operator preparation

Use a trusted Linux host controlled by the operator. Keep the home directory and keyring private and backed up securely. The following are command templates; replace placeholders only after the coordinator publishes the official chain ID and genesis procedure.

```bash
./sobyad version
export SOBYA_HOME="$HOME/.sobya-testnet"
mkdir -p "$SOBYA_HOME"
chmod 700 "$SOBYA_HOME"
./sobyad init "<YOUR_NODE_MONIKER>" --chain-id "<OFFICIAL_TESTNET_CHAIN_ID>" --home "$SOBYA_HOME"
./sobyad keys add "<YOUR_VALIDATOR_KEY_NAME>" --keyring-backend file --home "$SOBYA_HOME"
```

Each operator generates their own keys locally. Never ask an operator to send their mnemonic or private key to the coordinator. Only public account addresses and signed gentx files are needed for genesis coordination.

## Genesis coordination

The coordinator must publish one authoritative procedure for collecting validator public addresses and signed gentx files:

1. Collect each operator's public validator account address.
2. Prepare one genesis state with the agreed chain ID and initial `asobya` allocations.
3. Distribute the same pre-launch genesis to operators for gentx creation.
4. Each operator creates a gentx locally using their own keyring and the agreed self-delegation amount.
5. The coordinator validates and collects the signed gentx files, then produces the final genesis.
6. Publish the final genesis and its SHA-256 checksum. Every operator must verify the checksum and use exactly that file.
7. Validate the final genesis and validator set independently before launch.

The exact gentx flags, self-delegation amount, account funding, and genesis validation commands must be tested against the release binary and agreed by all operators before this procedure is used. Do not substitute a CI test genesis for the public genesis.

## Network configuration and launch

- P2P commonly uses TCP `26656`; verify actual generated `config.toml` values and firewall rules on every host.
- CometBFT RPC commonly uses TCP `26657`; keep it bound to localhost or protect it behind authenticated, rate-limited infrastructure.
- EVM JSON-RPC commonly uses TCP `8545`; expose it only after the API, rate limits, TLS/reverse proxy and security policy are reviewed.
- Configure persistent peers using actual node IDs and public P2P addresses supplied by operators. Do not publish guessed peer IDs or placeholder addresses as live endpoints.
- Keep validator signing keys local to their validator process and operator.
- Configure monitoring, disk-space alerts, time synchronization, backups, upgrade coordination, and incident recovery before launch.

Do not declare the network live until at least two independently hosted nodes connect over public P2P, agree on chain ID and height, produce blocks, and complete a transfer between separately controlled wallets.

## What this guide does not authorize

This guide does not authorize a mainnet launch, token sale, public token value claims, or use of GitHub Actions as permanent node hosting. CI runners are temporary and must not hold production validator keys.
