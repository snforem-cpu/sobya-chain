# SOBYA BUY API

Cloudflare Worker backend for the original manual SOBYA purchase-request desk.

## Public manual endpoints

- `GET /health` — service and database health.
- `GET /api/manual/price` — current owner-maintained SOBY reference price.
- `POST /api/manual/orders` — stores a manual purchase request for owner review.

The manual order request accepts a SOBY amount, payment network, payment asset/currency, amount paid, transaction reference, and buyer EVM address. The payment network and asset are entered by the buyer; the endpoint does not restrict the request to one chain or token.

## Manual fulfilment

Submitting an order does not prove that payment was received and does not automatically transfer SOBY. The owner must independently review the payment using the appropriate network explorer or wallet, then fulfil an approved order manually.

The owner desk uses authenticated owner challenges for order review and protected settings. Never place a private key, seed phrase, RPC credential, or admin token in source control or browser code.

## Database

The D1 migrations create the manual order records, price settings, inventory state, quote/order tables used by other disabled commerce paths, and audit records. The public manual order endpoint stores requests with status `submitted`; it does not mark payments as verified.

## Tests

Run the API test suite with Node.js 20 or later:

```sh
npm test
```

Automatic checkout and automatic payouts are not enabled by the manual purchase page.
