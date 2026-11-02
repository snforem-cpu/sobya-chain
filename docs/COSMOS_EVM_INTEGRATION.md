# SOBYA Cosmos EVM Integration Plan

Status: design and compatibility assessment only. Cosmos EVM is not yet wired
into the SOBYA application, and no EVM JSON-RPC endpoint is available.

## Candidate dependency baseline

The candidate is `github.com/cosmos/evm v0.6.0`.

The release's root module declares:

- Cosmos SDK `v0.53.6` — exact match with SOBYA.
- CometBFT `v0.38.21` — exact match with SOBYA.
- IBC-Go `v10.3.1-0.20250909102629-ed3b125c7b6f` — SOBYA currently uses
  `v10.4.0`; Go module version selection and the EVM package build must be
  verified before adoption.
- Go-Ethereum `v1.15.11` with the Cosmos-maintained replacement
  `github.com/cosmos/go-ethereum v1.16.2-cosmos-1`.

The module versions appear compatible at the SDK and CometBFT layers, but this
is not proof that the full SOBYA app can import and initialize the EVM stack.
The EVM package graph, IBC integration, Go-Ethereum replacement, and app wiring
must be tested in CI before the dependency is added to the production app.

## Required application integration

A complete integration must implement and test all of the following together:

1. EVM encoding, Ethereum-compatible account/address handling, and EVM chain ID.
2. EVM keeper, fee-market keeper, ERC-20 keeper, store keys, and required module
   accounts and permissions.
3. EVM ante handling and transaction decoding/encoding so Cosmos and Ethereum
   transactions are both accepted safely.
4. EVM module lifecycle and genesis initialization in the correct order.
5. Ethereum JSON-RPC, WebSocket configuration, API allow-list, and operational
   security limits.
6. Required EVM precompiles and the intended IBC transfer/callback integration.
7. A single canonical native SOBY supply across Cosmos bank and EVM/ERC-20
   interfaces. Tests must prove that conversions and transfers cannot create a
   second independently spendable supply.
8. Fixed-supply enforcement across Cosmos minting, EVM mint paths, genesis,
   governance parameter changes, and upgrades.
9. End-to-end tests for Cosmos sends, EVM native transfers, contract deployment,
   ERC-20 representation, fee charging, staking, and IBC behavior.

## Current SOBYA architecture consideration

SOBYA currently uses Cosmos SDK App Wiring/depinject in `app/app.go` and
`app/app_config.go`. The Cosmos EVM reference application in v0.6.0 uses a
substantial manually wired BaseApp application. Integration therefore requires
an explicit architecture decision: adapt the EVM keepers and modules to the
existing SOBYA app wiring, or deliberately port the reference application's
application construction and then re-apply SOBYA's custom denomination,
fixed-supply, genesis, IBC, and governance rules. Merely adding the EVM module
to `go.mod` would not enable EVM support.

## Token precision and staking

The feature branch now uses 18 decimal places and an arbitrary-precision
1-billion-SOBY cap. The native base denomination is `asobya`, and the staking
power reduction is `10^18`. This matches the standard EVM gas-token precision.
The app still needs an integration-level test proving the same denomination
and amount semantics are used by the EVM keeper and Ethereum JSON-RPC.

## IDs and wallet metadata

The Cosmos chain ID and EVM chain ID are different values. Neither production
ID is assigned in this document. The EVM chain ID must be checked for collision
and chosen before the first public testnet genesis is created; after launch it
must not be casually changed.

Wallet compatibility targets are:

- EVM JSON-RPC wallets such as MetaMask and Rabby, after a stable public RPC
  and correct EVM chain ID are available.
- Cosmos wallets such as Keplr, after the Cosmos chain metadata, REST/gRPC/RPC
  endpoints, address derivation, and chain registry submission are prepared.
- Trust Wallet and Phantom only after their current network/token listing
  requirements are satisfied.

No wallet can be promised universal support. A repository logo file alone does
not cause a wallet to display the network or token.

## Acceptance gates

Do not mark Cosmos EVM integration complete until:

- the EVM compatibility workflow passes using the pinned candidate version;
- SOBYA's application builds and all unit/integration tests pass;
- a local network starts with both Cosmos and Ethereum JSON-RPC enabled;
- an EVM wallet can query chain ID and native balance and submit a signed
  transaction;
- Cosmos and EVM transfers preserve one native supply and expected balances;
- two independent nodes synchronize and process both transaction formats;
- security, fee policy, validator economics, and production genesis are reviewed.
