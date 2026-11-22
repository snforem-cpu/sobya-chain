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

The example config is a template, not production configuration. The payout worker is invoked only after the deposit queue has been processed in each cycle; it can therefore see a newly finalized deposit in the same cycle. The quote provider keeps the agreed base reference price at 0.005 USDT per SOBY. It reads the native SOBY balance directly from the configured SOBYA HTTPS RPC at a finalized block for every quote, verifies chain ID and freshness, and derives pricing reference depth from spendable live SOBY inventory at the base price. No external USDT liquidity deposit, copied inventory balance, or manual demand snapshot is needed. Demand uses only completed ledger orders after both deposit and payout finality. Upward demand sensitivity is four times downward sensitivity by default: price rises faster than it falls. There is deliberately no upper price ceiling. The approved per-order cap is 500 USDT, the per-network daily cap is 10,000 USDT, and the fee is 1% (100 bps). The protected minimum SOBY reserve remains an explicit operator setting; missing or stale values fail closed. Do not enable live payouts with null or guessed risk settings.



### Pricing and limit units

- `baseReferencePriceUsdtPerSoby` is decimal USDT per 1 SOBY and remains `0.005` as the agreed starting reference.
- USDT order/daily limits use 6-decimal USDT base units. Pricing depth is derived from live spendable SOBY inventory; there is no configured upper price ceiling.
- `minimumInventoryBaseUnits` and `verifiedPayoutInventoryBaseUnits` use 18-decimal SOBY base units.
- `feeBps` is basis points (100 = 1%); the approved fee is 100 bps. The approved USDT caps are 500 USDT per order and 10,000 USDT per network per UTC day; the runtime rejects values above 1000 (10%).
- Demand uses only `complete` ledger orders, a state reached after the exact destination payout is independently verified final; source USDT base units are counted over a rolling 3600-second window. Uncompleted orders never influence demand.
- Inventory is read from the SOBYA RPC at a finalized block on each quote; its block timestamp must be no older than `inventorySnapshotMaxAgeSeconds`.

## Customer order page and quote API

The repository includes a browser order page at `cross-chain/custodial/order-ui/index.html` and a loopback-only API in `custodial_order_api.py`. The committed default enables only USDT→SOBY because the initial operating inventory is SOBY on the SOBYA network; SOBY→USDT remains disabled until external-chain USDT payout inventory is funded and verified.

- `GET /` serves the order page; `GET /api/networks` returns supported networks and decimals.
- `POST /api/quote` returns a preview from the injected quote provider; it does not create an order or reserve inventory.
- `POST /api/orders` recalculates the quote and creates the order in SQLite. The response includes the exact shared inventory address, exact amount, order ID, and a per-order access token.
- `GET /api/orders/{order_id}` and `POST /api/orders/{order_id}/deposit-proof` require that per-order token. The order's quote expiry is persisted; deposit proofs submitted after expiry are rejected. Deposit proof submission accepts only the transaction ID/signature and exact event/instruction index; the verifier derives all other expected fields from the stored order.
- Requests are size-limited and rate-limited. The API refuses non-loopback binds and must only be exposed through a trusted TLS reverse proxy.

To enable it, set `orderApiEnabled=true`, set `SOBYA_ORDER_API_ACCESS_SECRET` to a random secret of at least 32 bytes, and configure the quote provider inputs. For USDT→SOBY, the quote provider verifies SOBYA payout inventory live at a finalized RPC block; it does not trust the static `payoutInventoryVerified` flag. External destination networks still require `payoutInventoryVerified=true` after their exact funded USDT payout wallet is independently checked. To enable SOBY→USDT later, first verify and fund each intended external USDT inventory wallet and explicitly add `soby_to_usdt` to `enabledSwapDirections`. Quote creation fails closed until the maximum order, daily per-network intake cap, fee, and protected SOBY reserve are set, and a live finalized SOBYA balance is available. Each order quote checks current-day USDT intake and outstanding SOBY payout reservations in the durable ledger; expired, unsubmitted quotes release reservations. Quote checks and order insertion share a SQLite `BEGIN IMMEDIATE` transaction, serializing reservations across processes. The CI suite covers fee math, uncapped asymmetric demand pricing, daily and order caps, stale inventory, and reserve protection. The example configuration leaves the API disabled. Do not accept deposits or expose the page publicly until the pricing inputs and TLS proxy are configured and verified.
