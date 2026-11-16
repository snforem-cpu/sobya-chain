# SOBYA BUY API — implementation stage

This Cloudflare Worker is a separate backend for the static GitHub Pages portal.
It does not use or modify the experimental `cloudflare-relay` validator transport.

## Current safety state

- Sales are hard-disabled by default (`SALE_ENABLED = false`).
- `GET /health` reports service health and explicitly reports that commerce is not ready.
- All `/api/*` commerce endpoints return HTTP 503 until the complete payment and payout pipeline is implemented.
- No private key, seed phrase, RPC credential, or admin token belongs in source control.
- The Worker does not accept or custody payments in this stage.

## Database

The initial D1 migration creates:
- Inventory state
- Ten-minute quote records
- Orders with a unique payment transaction constraint per chain
- Append-only audit events

Create a D1 database in Cloudflare, configure its binding in `wrangler.toml`, then apply migrations with Wrangler. Do not enable sales.

## Pricing engine

`src/pricing.js` is a deterministic, dependency-free calculation module. The opening reference price is $0.005 per SOBY. The policy has **no artificial upper price ceiling**: verified demand growth and inventory depletion can raise the calculated target without a configured maximum. A minimum-price floor remains an explicit input.

The calculation uses verified rolling 24-hour demand relative to a baseline, remaining inventory, and separate upward/downward smoothing. Positive demand growth is not capped; demand contraction is bounded so the target remains positive. If the calculation exceeds JavaScript's supported numeric range, it fails safely instead of returning an invalid number.

**Important integration rule:** calculate and persist a new price only as part of processing a newly verified purchase. Do not recalculate and compound the price on page loads, quote refreshes, or periodic polling. Pending, failed, unverified, or replayed payments must never contribute to demand or consume inventory.

The weights, smoothing rates, minimum price, demand baseline, and production data source still require explicit production configuration and review. The example values in tests are test fixtures only, not approved production settings. Removing the upper ceiling does not itself guarantee a $100 price; that can only result from sustained, genuine demand and the actual available supply.

Run tests with Node.js 20 or later:

```sh
npm test
```

## Not production-ready

Before a purchase endpoint can be enabled, implementation and verification are still required for:
1. Trusted ETH/USD and BNB/USD oracle reads and USDT depeg handling.
2. Exact quote conversion and decimal-safe integer arithmetic.
3. Ethereum USDT, ETH and BSC BNB transaction verification from independent RPC sources.
4. Required confirmation depth, replacement/reorg handling and payment replay protection.
5. Atomic inventory reservation and quote/order expiry.
6. A separately funded, dedicated SOBYA payout signer; never expose the Reserve wallet's private key.
7. Per-order and daily spending limits, signer pause, reconciliation and monitoring.
8. End-to-end tests on all payment rails, including Solana SOL, and SOBYA payout.

Do not set `SALE_ENABLED=true` or expose a payment address as an instruction to pay until every item above is complete and reviewed.
