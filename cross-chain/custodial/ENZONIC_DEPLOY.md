# Enzonic deployment

Deploy from the branch `enzonic-order-api` for review and validation. The implementation is based on `enzonic-swap-worker` and includes the finalized-deposit runtime plus the order/quote API.

## Required Enzonic settings

- Runtime: **Python 3.12**.
- Main file: `cross-chain/custodial/enzonic_start.py`.
- Install dependencies from the repository-root `requirements.txt`, which includes `cross-chain/custodial/requirements.txt`.
- Keep private keys, seed phrases, keystore contents, RPC credentials, and passphrases out of GitHub and source files.

## Order and quote API

The API is implemented in `order_api.py` and runs in the same process as the unified custodial runtime when `api.enabled=true`.

- `GET /health` — process health only; it does not imply deposits or payouts are enabled.
- `POST /v1/quotes` — creates a persistent order and a time-limited quote.
- `GET /v1/orders/{order_id}` — returns the order, quote, and deposit-proof queue status.
- `POST /v1/orders/{order_id}/deposit` — accepts `transaction_id` and the exact `event_index` (EVM log index, TRON log index, or Solana instruction index).

Quote request fields:

```json
{
  "direction": "usdt_to_soby",
  "source_network": "ethereum",
  "destination_network": "sobya",
  "source_wallet": "USER_SOURCE_ADDRESS",
  "destination_wallet": "USER_SOBYA_ADDRESS",
  "source_amount_base_units": 1000000
}
```

For the reverse direction use `direction=soby_to_usdt`, `source_network=sobya`, and select `ethereum`, `tron`, or `solana` as `destination_network`. Amounts are integer base units: USDT uses 6 decimals and native SOBY uses 18 decimals. The quote response supplies the shared inventory deposit address, destination amount, fee field, price, expiry, and order ID. The current fee defaults to zero until the fee policy is completed in step 3.

The deposit endpoint accepts:

```json
{
  "transaction_id": "CHAIN_TRANSACTION_HASH_OR_SIGNATURE",
  "event_index": 0
}
```

The API binds that proof to the stored order and queues it in the same durable SQLite table used by the worker. The verifier independently checks the transaction, sender, exact asset, amount, recipient, event/instruction index, and finality. A queued or pending proof is not a completed deposit; payout remains blocked until the worker advances that order to `deposit_final`. The status endpoint exposes queue state and retry information.

## Runtime safety and network model

The API is **disabled by default** (`api.enabled=false`). To start it, the operator must explicitly enable the top-level and relevant per-network deposit-watch gates, configure HTTPS RPC endpoints, and set `api.enabled=true`. The API binds to `127.0.0.1:8080` by default. For public client access, place it behind an operator-managed HTTPS reverse proxy with request controls; do not expose the plain HTTP listener directly to the internet.

The order model uses the same shared inventory wallet on each chain. No unique deposit addresses, balance-delta inference, automatic bridges, or wallet signing are used by the API. The API never signs or broadcasts transactions. The payout worker still runs only after deposit verification and only processes orders in `deposit_final`.

For a first process check, leave all wallet, RPC, and passphrase environment variables unset. The launcher creates a local config from the disabled example. API, deposit watching, and payouts remain disabled.

## Before accepting real customer orders or enabling payouts

Do not publish the API or accept real deposits until the operator has configured and verified each source-chain RPC, exact inventory addresses, chain/token identities, quote price, limits and fee policy, HTTPS ingress, and durable backups. Do not enable `featureEnabled` or any network payout flag until encrypted keystores and passphrases are installed as runtime secrets, fee balances and inventory are verified, and controlled end-to-end tests pass.

This code implementation is not a live exchange launch. The Enzonic process must still be deployed and verified in step 5; live deposits and payouts remain disabled until the later release gates are completed.
