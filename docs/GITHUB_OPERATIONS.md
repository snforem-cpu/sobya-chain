# SOBYA GitHub Operations

This repository branch is the maintenance and test branch:
`maintenance/verify-build`.

The `main` branch is intentionally not changed by these procedures.

## What GitHub can do

GitHub Actions can build the SOBYA node, run automated tests, create a fresh
single-validator local network, verify RPC and block production, and publish
short-lived downloadable build artifacts. Scheduled workflows provide
recurring checks.

GitHub-hosted runners are temporary CI machines. They are **not** persistent
blockchain validators, seed nodes, RPC servers, or public network infrastructure.
A workflow passing does not mean a public testnet is running.

## Automated workflows

- **SOBYA Project Verification**: extracts the source archive, verifies Go
  dependencies, runs the Go test suite, builds the node, and maintains the
  `usobya` denomination in the source archive.
- **SOBYA Localnet Smoke Test**: creates a new disposable local chain, starts
  one validator, checks RPC, waits for block production, and checks its
  `usobya` balance.
- **SOBYA Multi-Node Localnet**: uses SOBYA's native `multi-node` command to
  generate two validator homes with one canonical genesis, starts both
  validators as separate processes, and verifies RPC, P2P peer connections,
  synchronized block production, and the two-validator set. This runs on one
  temporary CI runner and is not an independently hosted public testnet.
- **SOBYA Node Build**: builds a Linux AMD64 node binary and uploads a
  `sobya-linux-amd64.tar.gz` artifact for 30 days. It runs manually, on
  relevant maintenance-branch changes, and weekly.

Open the repository's **Actions** tab, choose a workflow, then select
**Run workflow** to start a manual run. Download successful build artifacts
from the workflow run's **Artifacts** section.

## Public testnet readiness checklist

Do not announce a public testnet until all of the following are true:

1. A stable chain ID and a reviewed, reproducible genesis file are published.
2. At least two independently operated nodes can connect over P2P.
3. The P2P endpoint is reachable from outside the hosting network.
4. Nodes agree on chain ID and block height and remain synchronized.
5. A test transfer between separately controlled wallets succeeds.
6. Node operators have documented backup, restore, upgrade, and recovery
   procedures.
7. Validator signing keys are generated and kept by their operators. Never put
   mnemonics, validator private keys, or keyring files in Git, workflow logs,
   public artifacts, or repository secrets for routine CI.

## Network ports and exposure

For a Cosmos-SDK/Tendermint-style node, P2P commonly uses TCP port 26656 and
RPC commonly uses TCP port 26657. Confirm the actual values in the generated
node configuration before deployment. Expose P2P only as required. Keep RPC
bound to localhost or behind authenticated, rate-limited infrastructure unless
there is a deliberate and reviewed reason to expose it.

## Important limitations

- GitHub Actions jobs are time-limited and ephemeral.
- Workflow artifacts expire according to their retention setting.
- A localnet smoke test is not a multi-node public testnet.
- No workflow in this repository should be used to keep a validator running.
- Never store real validator keys or wallet secrets in CI.
- Changes are made on `maintenance/verify-build`; do not merge to `main`
  without explicit approval.
