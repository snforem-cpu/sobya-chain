# SOBYA GitHub Operations

Development and EVM integration work is being prepared on the isolated branch
`feature/cosmos-evm-logo-audit`. The repository's `main` branch is not changed
by this work.

## Canonical source

The tracked application in `sobya/` is the working source for feature-branch
validation. The root-level `26031` archive is an older generated source
snapshot and is not authoritative for the current token implementation. Do not
make protocol changes only in the archive.

The feature-branch validation workflow checks out the exact pushed commit,
validates that the archive can be extracted, and runs Go dependency checks,
tests, and builds against the tracked `sobya/` application. It does not commit
or push changes to any branch.

## What GitHub can do

GitHub Actions can build the SOBYA node, run automated tests, create disposable
local networks, and publish short-lived downloadable build artifacts.
GitHub-hosted runners are temporary CI machines. They are **not** persistent
blockchain validators, seed nodes, RPC servers, or public network infrastructure.
A workflow passing does not mean a public testnet is running.

## Token and EVM development status

- Native display token: `SOBY`.
- Native base denomination: `asobya`.
- Precision: 18 decimals.
- Maximum native supply: 1 billion SOBY, represented using arbitrary-precision
  integer arithmetic.
- Cosmos EVM `v0.6.0` is the candidate integration baseline because its Cosmos
  SDK and CometBFT versions match the working source. EVM module wiring,
  transaction ante handling, Ethereum JSON-RPC, ERC-20 representation, and
  precompile behavior still require implementation and end-to-end tests.
- The official logo is stored in `assets/logo/`; wallet display requires each
  wallet's own metadata and listing process.

## Public testnet readiness

Do not announce a public testnet until all of the following are true:

1. A stable Cosmos chain ID and EVM chain ID and a reviewed, reproducible
   genesis file are published.
2. At least two independently operated nodes can connect over public P2P.
3. The P2P endpoint is reachable from outside the hosting network.
4. Nodes agree on chain ID and block height and remain synchronized.
5. A test transfer between separately controlled wallets succeeds.
6. EVM JSON-RPC and Cosmos APIs are reachable and pass security checks.
7. Node operators have documented backup, restore, upgrade, and recovery
   procedures.
8. Validator signing keys are generated and kept by their operators. Never put
   mnemonics, validator private keys, or keyring files in Git, workflow logs,
   public artifacts, or routine CI secrets.

## Important limitations

- GitHub Actions jobs are time-limited and ephemeral.
- Workflow artifacts expire according to their retention setting.
- A localnet smoke test is not a multi-node public testnet.
- No workflow in this repository should be used to keep a validator running.
- Never store real validator keys or wallet secrets in CI.
- Do not merge the feature branch to `main` without explicit approval.
