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
