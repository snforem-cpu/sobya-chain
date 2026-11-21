# Durable cross-chain order ledger (prototype)

`order_ledger.py` adds a SQLite-backed monotonic evidence ledger. It is
intended to sit behind an authenticated coordinator service, after chain
observers have independently verified their evidence.

## State transitions

`QUOTED -> SOURCE_FUNDED -> DESTINATION_PAID`

- `register_quote` stores an immutable order quote and its digest.
- `record_source_deposit` requires every source and destination field to match
  the registered quote, then records the source transaction/event uniquely.
- `record_destination_payout` is rejected until the source deposit is recorded
  and all payout bindings match the quote.
- Unique constraints prevent reusing the same source event or destination event
  for another order. Each accepted transition is recorded in an append-only
  event table within the same SQLite transaction.

## Explicit boundaries

- The ledger trusts its caller to pass evidence returned by the chain-specific
  verifiers and, in production, an independent observer quorum. It does not
  authenticate a quote signature or verify chain finality itself.
- `DESTINATION_PAID` means the destination payout evidence was recorded. It
  does not mean source USDT was claimed by the solver or that a source escrow
  released funds.
- There is intentionally no API to sign attestations, claim escrow, refund,
  withdraw, mint, or send transactions.
- SQLite is a local prototype database, not a horizontally scaled production
  datastore. A production service needs authenticated APIs, migrations,
  backups, access controls, monitoring, rate limits, and recovery procedures.
- No server, RPC endpoint, private key, source-chain address, or production
  database is configured.

## Attestation payload preparation (no signer)

`attestation_payload.py` builds the EIP-712 payout typed-data/digest expected
by the Ethereum/TRON escrow state machine and the Borsh `AttestPayout`
instruction bytes expected by the Solana program. It performs serialization
only: no private keys, signature creation, transaction signing, or broadcast.
See `ATTESTATION_PROTOCOL.md` for exact fields and the trust boundary.

## Attestation payload preparation

The adjacent `attestation_payload.py` module creates deterministic EIP-712
Payout typed data/digests for Ethereum and TRON escrow domains, plus the Borsh
`AttestPayout` instruction bytes for Solana. It contains no signing keys,
signature generation, transaction submission, or claim automation. See
`ATTESTATION_PROTOCOL.md`; live signing remains disabled pending external
review and chain-specific integration testing.

## Fail-closed admission guard

`admission.py` adds an in-process boundary for a future local coordinator API.
Construct `ReadinessAdmissionGuard(monitor, ledger)` with the live supervisor
`Monitor` instance and the SQLite ledger:

- `register_quote` requires a fresh positive `monitor.admission(source, "sobya")`
  result before recording a new quote.
- `record_source_deposit` repeats the readiness check immediately before
  recording already-verified source-deposit evidence. A timeout, exception,
  malformed result, missing network, stale snapshot, or unhealthy source or
  destination denies admission.
- `record_destination_payout` deliberately does not use the admission gate:
  it allows completion of an already-funded order while new orders are paused.

This is a library guard, **not yet an HTTP quote/order API** and not a complete
production coordinator. The future API must call these guarded methods rather
than accessing the ledger directly. It must authenticate callers, verify quote
signatures and observer evidence before passing them in, reserve solver
inventory atomically, enforce per-order/global limits and rate limits, and
keep recovery/refund paths available. A readiness check and SQLite write are
not one atomic operation with node health; deployments must fail closed and
recheck immediately before each admission step. The guard does not sign,
broadcast, claim escrow, or move funds.

Run its focused tests from this directory:

```sh
python -m unittest -v test_admission.py test_order_ledger.py
```

## Local coordinator orchestration and solver inventory

`coordinator.py` adds a local orchestration boundary. It requires injected,
chain-specific verifier callbacks to return the literal boolean `True` before
it will pass quote, source-deposit, or destination-payout evidence onward.
Verifier exceptions and false/ambiguous results fail closed. The quote path
then calls the readiness guard and atomically reserves the exact SOBY payout
amount against the named solver's inventory.

The SQLite ledger now supports:
- `set_solver_inventory(solver, total_units)`: provision total SOBY inventory
  in 18-decimal base units; it cannot reduce total below active reservations.
- `available_solver_inventory(solver)`: return unreserved units.
- `register_quote_with_inventory(quote)`: in one SQLite transaction, require
  enough unreserved inventory, register the order, create its reservation,
  and increment reserved units. Concurrent quote attempts cannot reserve the
  same units twice.
- When verified destination payout evidence is recorded, the active
  reservation is consumed and total inventory is reduced by the payout amount.

This is still **not a network-facing HTTP API**. It has no HTTP listener,
caller authentication, real EIP-712/Solana signature verifier, live observer
binding, key management, transaction submission, or escrow claim automation.
The injected verifier callbacks are security-critical and must be implemented
and reviewed against the chain-specific observer/attestation formats before
deployment. Inventory provisioning is a trusted local operator action, not a
user-facing endpoint. Do not expose SQLite or these methods directly to
untrusted callers.

Tests:

```sh
python -m unittest -v test_admission.py test_coordinator.py test_order_ledger.py
```

## Authenticated loopback HTTP API

`http_api.py` exposes a small HTTP adapter around `LocalCoordinator`:

- `POST /v1/quote-previews`: create an unsigned, inventory-aware price preview; it does not reserve inventory or accept an order.
- `POST /v1/quotes`: submit a signed quote; signature verifier, readiness gate,
  and atomic solver inventory reservation must all succeed.
- `POST /v1/source-deposits`: submit source-deposit evidence and its proof;
  the injected observer verifier must accept it, then both source and SOBYA
  readiness are checked again before ledger acceptance.
- `POST /v1/destination-payouts`: submit payout evidence and proof for an
  existing funded order; verifier is required, but new-order readiness is not
  used to block completion.
- Every route requires `Authorization: Bearer <token>`; token must be at least
  32 UTF-8 bytes. Requests are JSON with strict record schemas and a bounded
  body (64 KiB default). The server only binds to a literal loopback address.

The server is created programmatically with `create_server(...)`; pass an `InventoryAwareQuotePricer` as `quote_pricer` to enable the unsigned preview route. The route returns explicit `signed: false` and `reserved: false` flags. It is not
started automatically and has no default token or default verifier. The
application integrator must provide secure token loading and audited
chain-specific verification callbacks. Do not bind it to a public interface,
commit a bearer token, or expose it through a reverse proxy. The current API
does not include quote pricing, automatic quote signing, RPC calls, relaying,
escrow claims, refunds, or an inventory balance oracle.

HTTP API tests:

```sh
python -m unittest -v test_http_api.py
```


## Same-origin DEX quote gateway

See [BROWSER_GATEWAY.md](BROWSER_GATEWAY.md) for the loopback browser gateway, origin allowlist, reverse-proxy route, process configuration, and focused tests. The gateway exposes only unsigned, non-reserving quote previews; it does not enable deposits or settlement.

## EIP-712 solver quote verification

`eip712_quote_verifier.py` now implements the escrow's exact `Order` EIP-712
type hash and domain (`SOBYA Cross-Chain Escrow`, version `1`, pinned source
chain ID, pinned escrow address). It recovers the signer using secp256k1,
enforces canonical low-s signatures and accepts a quote only when the recovered
address equals the configured solver address. Ethereum and the TRON TVM wrapper
use the same Solidity order digest; each must have its own configured chain ID
and deployed escrow address. Solana uses the solver as a transaction co-signer
on the Fund instruction, and its observer checks that signer in the finalized
transaction. The service never receives a solver private key.

Example wiring:

```python
quote_signature_verifier = Eip712QuoteVerifier({
    "ethereum": Eip712QuoteDomain(chain_id=ETHEREUM_CHAIN_ID, verifying_contract=ETH_ESCROW),
    "tron": Eip712QuoteDomain(chain_id=TRON_TVM_CHAIN_ID, verifying_contract=TRON_ESCROW),
})
# Pass quote_signature_verifier.verify as verify_quote_signature to create_server.
```

All chain IDs and escrow addresses must come from verified private deployment
configuration. No guessed defaults are provided.

## Finalized observer routers

`cross-chain/observer/source_observer_router.py` composes the existing
Ethereum, TRON Solidity Node, and Solana finalized source observers. Its
coordinator callback accepts only a minimal transaction identifier/signature,
loads the immutable registered quote, queries the configured self-hosted node,
and compares every evidence field with the exact finalized on-chain order.
Solana derives the config PDA, order PDA, and associated legacy-SPL escrow
token account itself; callers cannot choose those addresses.

`destination_payout_router.py` composes the SOBYA `SettlementVerifier`. It
requires pinned bytes32 source-chain/escrow/asset identities and verifies the
canonical receipt, configured settlement contract, transaction sender/value,
confirmation depth, exact `PayoutExecuted` event, and all order bindings.

Example composition:
```python
lookup = lambda order_id: quote_from_ledger(ledger, order_id)
source_verifier = SourceObserverRouter(
    quote_lookup=lookup, ethereum=ETHEREUM_NODES, tron=TRON_NODES,
    solana=SOLANA_NODE,
)
payout_verifier = DestinationPayoutRouter(
    quote_lookup=lookup, settlement=SOBYA_SETTLEMENT,
    source_identities=PINNED_SOURCE_IDENTITIES,
)
# Pass source_verifier and payout_verifier to create_server.
```

The routers are read-only. They do not start nodes, sign, broadcast, or claim
escrow. They require configured SOBYA-operated node RPC clients and pinned
identities. Unit/mock tests are not live-chain or testnet integration evidence.

## Inventory-aware quote pricing

`pricing.py` converts integer USDT base units to integer SOBY base units using
an explicitly configured rational reference rate (USDT base units per whole
SOBY), deducts a configured fee in basis points, enforces source amount limits,
and refuses quotes exceeding the solver's unreserved ledger inventory.
It sets bounded quote/refund deadlines. The coordinator still performs the
atomic inventory reservation when the signed quote is submitted, preventing
concurrent quotes from promising the same SOBY twice.

The rate is an operator-maintained reference input, **not a live market price
or price oracle**. The pricer does not sign quotes; the solver must sign the
resulting EIP-712 order with its own wallet. Inventory values must be reconciled
against finalized SOBYA balances before production. No live quote endpoint is
enabled by this change.


## Exact SOBY base-unit inventory storage

Solver inventory and reservation amounts are stored as decimal TEXT, then
parsed and arithmetically updated as Python integers inside the same SQLite
write transaction. This avoids SQLite's signed 64-bit INTEGER ceiling, which
is far below the base-unit representation of the network's token supply.
Initialization migrates the earlier INTEGER inventory tables transactionally
and preserves existing totals and active reservations. Tests cover a
150,000,000 SOBY-scale balance and legacy-table migration.


## Fully wired local runtime

`runtime.py` is the composition root. It constructs the EIP-712 quote verifier,
source and destination observer routers, readiness admission guard, inventory
pricer, and authenticated loopback HTTP server as one object. The caller must
supply the live supervisor monitor, ledger, private RPC clients, pinned
Ethereum/TRON chain IDs and escrow addresses, Solana program/mint/genesis
identity, SOBYA settlement contract and source bytes32 identities, and a bearer
token loaded from the local secret store or process environment.

The module returns a server object but **does not start it**. Before importing
it from a deployment process, expose both local modules on the Python path,
for example from `cross-chain/coordinator`:

```sh
PYTHONPATH=.:../observer python your_local_launcher.py
```

The launcher must keep the server bound to loopback, start it under a
supervised process manager, and provide only SOBYA-operated private RPC
endpoints. No node addresses, genesis hashes, escrow addresses, API tokens,
or keys are populated with guessed defaults.

## Finalized SOBYA vault reservation adapter

`sobya_vault_connector.py` now supplies the concrete adapter required by
`LocalCoordinator.issue_quote`. It calls the pinned SOBYA EVM RPC, verifies
the chain ID and deployed vault bytecode, builds the exact
`reserve(bytes32,address,uint128,uint64)` call, and delegates transaction
signing to a caller-supplied local signer callback. It then verifies the
broadcast transaction fields, successful receipt, canonical block, finalized
checkpoint, configured confirmation depth, exact `InventoryReserved` event,
and the finalized `reservations(orderId)` storage readback. A mismatched or
unfinalized reservation fails closed.

The module does not load a key, write a key file, or expose a signing endpoint.
The signer callback must use a locally protected keystore or hardware signer
on SOBYA-operated infrastructure and return the signed raw transaction as
hex. Never implement that callback by placing a private key in this repository,
the browser, the quote API, or observer configuration.

Integration shape (the runtime accepts either the adapter object or its
`reserve` method):

```python
from settlement_observer import JsonRpc
from sobya_vault_connector import SobyaVaultReserver

vault = SobyaVaultReserver(
    JsonRpc("http://127.0.0.1:8545"),
    expected_chain_id=357812033857,
    vault_address=PINNED_DEPLOYED_VAULT,
    signer=local_keystore_signer,
    confirmations=2,
)
server = build_local_server(
    # existing pinned observer, ledger, quote and readiness arguments
    reserve_onchain_inventory=vault,
)
```

`PINNED_DEPLOYED_VAULT` and `local_keystore_signer` are deployment inputs,
not repository defaults. No vault address or signer is guessed here. Run the
focused adapter tests with:

```sh
python -m unittest -v test_sobya_vault_connector.py
```

This adapter closes the transaction-submission interface in code; it does
not mean a vault has been deployed, funded, or configured on SOBYA Mainnet.


## Finalized SOBYA vault inventory reconciliation

The coordinator's inventory reader must query the **pinned
`SobyaSolverInventoryVault.available(solver)`** view at the EVM `finalized`
block tag. Reading `eth_getBalance(solver)` is not sufficient: native SOBY
held in the solver wallet is not necessarily deposited in the inventory vault
and cannot be paid by the settlement contract.

`observer/solver_balance_reader.py` therefore validates the configured SOBYA
chain ID and deployed vault code, then reads the vault's spendable inventory.
The runtime requires this reader and the transaction adapter to use the same
vault address and SOBYA RPC endpoint. The pricing layer takes the minimum of
the finalized on-chain spendable amount and the local ledger's spendable
amount. Because the vault view already subtracts on-chain reservations, the
pricing layer does not subtract those reservations a second time.

A solver must deposit native SOBY into the vault before its inventory can be
quoted. A wallet balance, an operator-entered ledger total, or a successful
unit test is not evidence that vault inventory is funded.
