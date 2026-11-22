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

The example config is a template, not production configuration. The payout worker is invoked only after the deposit queue has been processed in each cycle; it can therefore see a newly finalized deposit in the same cycle. The quote provider requires an operator-approved reference depth, price floor/ceiling, per-order cap, per-network daily cap, fee (0–1000 bps), and protected minimum SOBY reserve. It reads the native SOBY balance directly from the configured SOBYA HTTPS RPC at a finalized block for every quote, verifies the chain ID and freshness, and derives the demand snapshot from ledger orders only after both deposit and payout finality have been recorded. No manually copied inventory balance or demand snapshot is accepted. Missing, stale, or inconsistent values fail closed. The reference depth is a pricing input only; it is not an external USDT payout balance and does not require funding USDT inventory. Do not enable live payouts with null or guessed values.



### Pricing and limit units

- `baseReferencePriceUsdtPerSoby`, `priceFloor`, `priceCeiling` are decimal USDT per 1 SOBY.
- `referenceLiquidityUsdtBaseUnits` and all USDT order/daily limits use 6-decimal USDT base units. This is reference pricing depth, not an external USDT balance.
- `minimumInventoryBaseUnits` and `verifiedPayoutInventoryBaseUnits` use 18-decimal SOBY base units.
- `feeBps` is basis points (100 = 1%); the runtime rejects values above 1000 (10%).
- Demand uses only `complete` ledger orders, a state reached after the exact destination payout is independently verified final; source USDT base units are counted over a rolling 3600-second window. Uncompleted orders never influence demand.
- `inventoryObservedAtEpoch` is a Unix timestamp; the inventory snapshot must be no older than `inventorySnapshotMaxAgeSeconds`.

## Customer order page and quote API

The repository includes a browser order page at `cross-chain/custodial/order-ui/index.html` and a loopback-only API in `custodial_order_api.py`. The committed default enables only USDT→SOBY because the initial operating inventory is SOBY on the SOBYA network; SOBY→USDT remains disabled until external-chain USDT payout inventory is funded and verified.

- `GET /` serves the order page; `GET /api/networks` returns supported networks and decimals.
- `POST /api/quote` returns a preview from the injected quote provider; it does not create an order or reserve inventory.
- `POST /api/orders` recalculates the quote and creates the order in SQLite. The response includes the exact shared inventory address, exact amount, order ID, and a per-order access token.
- `GET /api/orders/{order_id}` and `POST /api/orders/{order_id}/deposit-proof` require that per-order token. The order's quote expiry is persisted; deposit proofs submitted after expiry are rejected. Deposit proof submission accepts only the transaction ID/signature and exact event/instruction index; the verifier derives all other expected fields from the stored order.
- Requests are size-limited and rate-limited. The API refuses non-loopback binds and must only be exposed through a trusted TLS reverse proxy.

To enable it, set `orderApiEnabled=true`, set `SOBYA_ORDER_API_ACCESS_SECRET` to a random secret of at least 32 bytes, and configure the quote provider inputs. The destination network must have `payoutInventoryVerified=true`, set only after its exact payout wallet balance is independently checked. The example keeps this flag false on every network, so it cannot issue customer orders by default. To enable SOBY→USDT later, first verify and fund each intended external USDT inventory wallet, set its `payoutInventoryVerified=true`, and explicitly add `soby_to_usdt` to `enabledSwapDirections`. Quote creation intentionally fails closed until all pricing and risk inputs are present: finalized demand snapshot, approved reference depth, floor/ceiling, maximum order, daily per-network intake cap, fee, minimum protected SOBY reserve, and a verified SOBYA inventory amount with an observation timestamp no older than the configured maximum age. Each quote checks current-day USDT intake and all SOBY orders/payouts created since the verified inventory snapshot in the durable order ledger. Quote-check plus order insertion is serialized to prevent concurrent requests from exceeding caps. The CI suite exercises fee math, price bounds, daily caps, order caps, stale inventory, and reserve protection. The example configuration leaves the API disabled. Do not accept deposits or expose the page publicly until the pricing inputs and TLS proxy are configured and verified.
