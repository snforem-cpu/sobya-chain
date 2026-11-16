# SOBYA BUY API — implementation stage

This Cloudflare Worker is a separate backend for the static GitHub Pages portal.
It does not use or modify the experimental `cloudflare-relay` validator transport.

## Current safety state

- Sales are hard-disabled by default (`SALE_ENABLED = false`).
- `GET /health` reports service health, D1 binding presence, and that commerce is not ready.
- `GET /api/price` exposes the D1-backed public price snapshot.
- All other `/api/*` commerce endpoints return HTTP 503 until the complete payment and payout pipeline is implemented.
- No private key, seed phrase, RPC credential, or admin token belongs in source control.
- The Worker does not accept or custody payments in this stage.

## Database

The D1 migrations create:
- Inventory state
- Ten-minute quote records
- Orders with a unique payment transaction constraint per chain
- Append-only audit events
- Persistent opening/current price and sale inventory state (`0002_pricing_state.sql`)
- A separate pricing-policy row, intentionally left unconfigured until production values are approved

Create the D1 database `sobya-buy-db` in Cloudflare, add the `DB` binding in `wrangler.toml`, then apply both migrations with Wrangler. The binding requires the actual D1 database ID from Cloudflare; do not put a guessed ID in source control. Example binding:

```toml
[[d1_databases]]
binding = "DB"
database_name = "sobya-buy-db"
database_id = "<YOUR_ACTUAL_D1_DATABASE_ID>"
migrations_dir = "migrations"
```

Do not enable sales.

## Pricing engine

`src/pricing.js` is a deterministic, dependency-free calculation module. The opening reference price is $0.005 per SOBY. The policy has **no artificial upper price ceiling**: verified demand growth and inventory depletion can raise the calculated target without a configured maximum. A minimum-price floor remains an explicit input.

The `GET /api/price` endpoint reads persistent pricing state from D1 and counts only orders with status `paid` as completed purchases. It reports 24-hour and 7-day verified demand, remaining sale inventory, and the current price. It returns the opening reference price while the production policy is incomplete; it never pretends that this is a live dynamic calculation. When a complete policy row is configured, it calculates a deterministic price from current verified demand and inventory without mutating stored price state on page refreshes.

Positive demand growth is not capped; demand contraction is bounded so the target remains positive. If the calculation exceeds JavaScript's supported numeric range, it fails safely instead of returning an invalid number. Pending, confirming, verified-but-not-paid, failed, or refunded orders do not contribute to demand.

The weights, smoothing rates, minimum price, demand baseline, and production data source still require explicit production configuration and review. The example values in tests are test fixtures only, not approved production settings. Removing the upper ceiling does not itself guarantee a $100 price; that can only result from sustained, genuine demand and the actual available supply.

The browser must also be configured with the deployed Worker base URL in `buy/config.js` (`apiBaseUrl`).

Run tests with Node.js 20 or later:

```sh
npm test
```

## Not production-ready

Before a purchase endpoint can be enabled, implementation and verification are still required for:
1. Trusted ETH/USD and BNB/USD oracle reads and USDT depeg handling.
2. Exact quote conversion and decimal-safe integer arithmetic.
3. Ethereum USDT, ETH, BSC BNB, and Solana SOL transaction verification from independent RPC sources.
4. Required confirmation depth, replacement/reorg handling and payment replay protection.
5. Atomic inventory reservation and quote/order expiry, including decrementing available sale inventory only after a completed payout.
6. A separately funded, dedicated SOBYA payout signer; never expose the Reserve wallet's private key.
7. Per-order and daily spending limits, signer pause, reconciliation and monitoring.
8. End-to-end tests on all payment rails and SOBYA payout.

Do not set `SALE_ENABLED=true` or expose a payment address as an instruction to pay until every item above is complete and reviewed.
