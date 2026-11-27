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

Additional feature-branch workflows exercise the 18-decimal localnet and
two-validator transfer path, and separately compile the candidate Cosmos EVM
v0.6.0 modules against SOBYA's Cosmos SDK/CometBFT dependency baseline. Passing
the EVM dependency check does not mean the EVM application has been integrated.

## What GitHub can do

GitHub Actions can build the SOBYA node, run automated tests, create disposable
local networks, and publish short-lived downloadable build artifacts.
GitHub-hosted runners are temporary CI machines. They are **not** persistent
blockchain validators, seed nodes, RPC servers, or public network infrastructure.
SOBYA Mainnet is already live; a workflow result applies only to the specific source commit and CI environment tested.

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

## Live Mainnet status\n\nSOBYA Mainnet is live with CometBFT chain ID `sobya-1` and EVM chain ID `357812033857`. Public endpoints are listed in the root README. GitHub Actions is used for source validation, builds and regression tests; CI runners are not production validator hosts. Local CI identifiers `777777` and `777778` are not production identifiers.\n\nUse the live validator onboarding guide for new operators. Do not create a replacement genesis or run a new-chain ceremony to join the existing network.\n