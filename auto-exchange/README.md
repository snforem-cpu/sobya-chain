# SOBYA Auto Exchange (isolated)

This is an independent project under `auto-exchange/`. It does not modify `buy/`, `dex/`, existing contracts, chain configuration, or live balances.

## Wallet and networks

- Inventory EVM address: `0xebdb899fFE84a89e1d576964b640491c135651AD`.
- Ethereum mainnet (chain ID 1): customer USDT deposits.
- SOBYA EVM (chain ID 357812033857): SOBY inventory/payout source.
- The same address is used on both networks; balances and transactions remain separate.

## Commercial policy recorded

- Opening price: 0.005 USDT per SOBY.
- Reference inventory: 1,000,000 SOBY (not a claim about live balance).
- Exchange fee: 1% (100 bps).
- Directional coefficients: 1000 upward / 250 downward (4:1).
- Quote validity: 10 minutes.
- No fixed maximum price; time alone does not move the price.

The absolute price-impact formula/normalizer for the 1000/250 coefficients has not been specified. The code deliberately does not invent one or calculate a live floating price.

## Implemented settlement core

`settlement.js` is a pure, side-effect-free matching module. It accepts a quote ledger and a decoded Ethereum USDT Transfer event, then checks:

1. Ethereum chain ID, sender, deposit address, USDT contract address and exact integer atomic-unit amount.
2. A single matching open quote (zero matches = unmatched; multiple = ambiguous/manual review).
3. The block timestamp falls within that quote's creation/expiry window.
4. Required confirmations have been reached.
5. The transaction hash + log index has not already been processed.

A successful match changes the quote to `paid` and returns `matched_paid_not_settled`. **It does not sign or send SOBY.** The transfer replay key is recorded in the returned ledger state. The caller must persist that state durably and serialize writers.

Tests cover exact matching, wrong chain/token/sender/recipient/amount, expiry, insufficient confirmations, duplicate logs and ambiguous quotes.

## Critical limitation — quote issuance and durable ledger

The matching core is now implemented, but the end-to-end exchange is NOT operational.

An ordinary ERC-20 transfer has no quote ID. Matching therefore depends on a pre-existing quote ledger that assigns a unique exact USDT atomic amount to one sender and one quote. The included `ledger.example.json` is only a schema example, not a live database. A static GitHub Pages page cannot safely write private durable orders to the repository, and a public workflow cannot accept arbitrary user quote requests while safely using a privileged repository token.

Before enabling real deposits, a trusted quote-issuance path must reserve unique amounts, persist quotes, prevent collisions/concurrent reuse, and expire/release reservations. The settlement runner must then persist its ledger atomically with single-writer protection. GitHub Actions can run scheduled jobs, but it is not a continuously available backend and scheduled runs may be delayed.

If that durable quote/ledger path cannot be provided within the no-paid-hosting constraint, the interface must remain quote-only/manual-review. Do not send customer funds to the inventory address for this Auto Exchange yet.

## Security state

- `tradingEnabled: false`.
- `payoutEnabled: false`.
- No private key, signing secret, live RPC signer, or automatic payout code is present.
- Never place a private key in frontend files, Git history, artifacts, or logs.
- Never run financial signing from untrusted pull-request workflows.
- No paid contract, paid hosting, or new paid service is part of the intended design.

## Tests

Run `npm test` from this directory. GitHub Actions workflow `.github/workflows/test-auto-exchange.yml` runs these isolated tests on changes to this directory.
