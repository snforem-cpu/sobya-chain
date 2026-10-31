# SOBYA Public Testnet Operator Guide (Preparation)

This document is an operational preparation guide, not an announcement that a
public testnet is live. A public launch remains blocked until independent
operators, public P2P reachability, a reviewed common genesis, and a successful
cross-node transfer have all been verified.

## Current tested baseline

The CI workflow `.github/workflows/multi-node-localnet.yml` currently proves:

- SOBYA's native `sobyad multi-node` command creates two validator homes.
- Both homes contain byte-identical genesis files and the same chain ID.
- Two node processes connect over P2P and each reports at least one peer.
- Both nodes produce blocks at the same height.
- The chain reports two validators.
- A signed `1000usobya` bank transfer between the two separately generated
  validator keyrings is committed and reflected in both account balances.
- The configured minimum fee in this test is `20usobya`; the test checks the
  sender's balance decreases by 1,020 and the recipient's increases by 1,000.

This is still a local CI network on one temporary runner. It does not establish
public Internet connectivity or independent hosting.

## Before announcing a public testnet

The coordinator and operators must agree on and publish:

1. A unique, stable testnet chain ID (do not reuse the CI chain ID).
2. The genesis time, initial validator set, initial account allocations, and
   denomination `usobya`.
3. The minimum gas price and transaction fee policy.
4. At least two independently operated validator or full-node hosts.
5. Public P2P addresses and persistent peer information.
6. A checksum (SHA-256) for the final, shared genesis file.
7. A support/contact channel and a clear statement that testnet tokens have
   no monetary value.

Do not put mnemonics, private validator keys, keyring directories, or wallet
secrets in this repository, CI artifacts, public issue comments, or logs.

## Operator preparation

Use a trusted Linux host controlled by the operator. Keep the home directory
and keyring private and backed up securely. The following are command templates;
replace placeholders only after the coordinator publishes the official chain
ID and genesis procedure.

```bash
# Confirm the binary is the release supplied by the project coordinator.
./sobyad version

# Create a private home and initialize the node.
export SOBYA_HOME="$HOME/.sobya-testnet"
mkdir -p "$SOBYA_HOME"
chmod 700 "$SOBYA_HOME"
./sobyad init "<YOUR_NODE_MONIKER>" --chain-id "<OFFICIAL_TESTNET_CHAIN_ID>" --home "$SOBYA_HOME"

# Generate your own validator/account key locally.
# Store the displayed recovery phrase offline and never share it.
./sobyad keys add "<YOUR_VALIDATOR_KEY_NAME>" --keyring-backend file --home "$SOBYA_HOME"
```

The key-generation step is intentionally performed by each operator on their
own host. Never ask an operator to send their mnemonic or private key to the
coordinator. Only the public account address and the signed gentx are needed
for the genesis coordination procedure.

## Genesis coordination (coordinator-controlled)

The coordinator must publish one authoritative procedure for collecting
validator public addresses and signed gentx files. The broad Cosmos-SDK flow
is:

1. Collect each operator's public validator account address.
2. Prepare one genesis state with the agreed chain ID and initial
   `usobya` allocations for all participating validator accounts.
3. Distribute the same pre-launch genesis to operators for gentx creation.
4. Each operator creates a gentx locally using their own keyring and the
   agreed self-delegation amount. No private key leaves the operator's host.
5. The coordinator validates and collects the signed gentx files, then
   produces the final genesis using `sobyad genesis collect-gentxs`.
6. Publish the final genesis and its SHA-256 checksum. Every operator must
   verify the checksum and use exactly that file before starting.
7. Validate the final genesis and validator set independently before launch.

The exact gentx flags, self-delegation amount, account funding, and genesis
validation commands must be tested against the release binary and agreed by
all operators before this procedure is used. Do not substitute the CI test
genesis for the public genesis.

## Network configuration and launch

- P2P commonly uses TCP `26656`; verify the actual generated
  `config.toml` values and firewall rules on every host.
- RPC commonly uses TCP `26657`; keep it bound to localhost or protect it
  behind authenticated, rate-limited infrastructure.
- Configure persistent peers using the actual node IDs and public P2P
  addresses supplied by operators. Do not publish guessed peer IDs or
  placeholder addresses as live endpoints.
- Keep validator signing keys local to their validator process and operator.
- Configure monitoring, disk-space alerts, time synchronization, backups,
  upgrade coordination, and incident recovery before launch.

The coordinator should not declare the network live until at least two
independently hosted nodes can connect over public P2P, agree on chain ID and
height, produce blocks, and complete a transfer between separately controlled
wallets.

## What this guide does not authorize

This guide does not authorize a mainnet launch, token sale, public token value
claims, or use of GitHub Actions as permanent node hosting. CI runners are
temporary and must not hold production validator keys.
