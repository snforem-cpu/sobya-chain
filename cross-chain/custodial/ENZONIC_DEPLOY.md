# Enzonic deployment

Deploy from the Git branch `enzonic-swap-worker` (PR #50 has been merged into this branch).

## Required Enzonic settings

- Runtime: **Python 3.12**. This entry point is Python; a Go runtime/container cannot execute it.
- Main file: `cross-chain/custodial/enzonic_start.py`
- Install dependencies from the repository-root `requirements.txt`, which includes `cross-chain/custodial/requirements.txt`.
- Keep private keys, seed phrases, keystore contents, and passphrases out of GitHub and source files.

## What this process actually runs

This entry point starts the **unified custodial runtime**: the durable order-bound deposit-proof queue is checked first, then the payout worker processes only orders already advanced to `deposit_final`. It still does not provide the public exchange interface or quote/order API. The API/order layer must submit each user's transaction hash/signature and exact log/instruction index to the deposit queue; the runtime never guesses orders from shared-wallet balance changes. A successful process start is not a live exchange launch.

For a first process check, leave all wallet, RPC, and passphrase environment variables unset. The launcher creates a local config from the disabled example. Deposit watching and payouts both remain disabled. To configure read-only deposit verification later, set top-level `depositWatchEnabled=true`, then enable only the required per-network `depositWatchEnabled` flags and provide their HTTPS RPC environment variables. This does not enable payout signing.

## Before enabling real payouts

Do not enable `featureEnabled` or any network flag until the full coordinator/API and deposit-watcher processes are deployed and supervised, the exact inventory addresses and chain IDs are verified, RPC endpoints respond correctly, encrypted keystores and passphrases are installed as environment/runtime secrets, fee balances and inventory are verified, and an end-to-end controlled test passes.

The example config is a template, not production configuration. The payout worker is invoked only after the deposit queue has been processed in each cycle; it can therefore see a newly finalized deposit in the same cycle. In particular, `referenceLiquidityUsdtBaseUnits` and operational limits must be set from verified values before quote creation. Do not infer these values or enable live payouts with null limits.


## Customer order page and quote API

The repository now includes a small browser order page at `cross-chain/custodial/order-ui/index.html` and a loopback-only API in `custodial_order_api.py`.

- `GET /` serves the order page; `GET /api/networks` returns supported networks and decimals.
- `POST /api/quote` returns a preview from the injected quote provider; it does not create an order or reserve inventory.
- `POST /api/orders` recalculates the quote and creates the order in SQLite. The response includes the exact shared inventory address, exact amount, order ID, and a per-order access token.
- `GET /api/orders/{order_id}` and `POST /api/orders/{order_id}/deposit-proof` require that per-order token. The order's quote expiry is persisted; deposit proofs submitted after expiry are rejected. Deposit proof submission accepts only the transaction ID/signature and exact event/instruction index; the verifier derives all other expected fields from the stored order.
- Requests are size-limited and rate-limited. The API refuses non-loopback binds and must only be exposed through a trusted TLS reverse proxy.

To enable it, set `orderApiEnabled=true`, set `SOBYA_ORDER_API_ACCESS_SECRET` to a random secret of at least 32 bytes, and configure the quote provider inputs. Quote creation intentionally fails closed until the finalized demand snapshot, verified reference liquidity, and operator-approved `feeBps` are present. The example configuration leaves the API disabled. Do not accept deposits or expose the page publicly until the pricing inputs and TLS proxy are configured and verified.
