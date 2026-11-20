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
