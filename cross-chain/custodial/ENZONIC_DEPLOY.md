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

## Four-network inventory and key preparation

The four shared inventory networks are Ethereum mainnet (USDT ERC-20, 6 decimals), TRON mainnet (USDT TRC-20, 6 decimals), Solana mainnet-beta (USDT SPL mint, 6 decimals, legacy Token Program), and SOBYA Mainnet (native SOBY, 18 decimals; EVM chain ID 357812033857). The configured Ethereum USDT contract, TRON USDT contract, and Solana USDT mint are pinned in `config.example.json`; do not substitute token contracts or mints.

Each network has its own encrypted keystore file and passphrase environment variable. Create each file locally with `python -m cross-chain.custodial.inventory_keystore_cli` only if the repository is installed as a package; otherwise run the CLI from `cross-chain/custodial` with `python inventory_keystore_cli.py --network NETWORK --file /secure/path/NETWORK.key`. The CLI prompts for the private key without echoing it, derives and prints only the public address, then encrypts the key with scrypt + XSalsa20-Poly1305 and writes an owner-only 0600 file. Use a distinct keystore per network, compare its printed public address character-for-character with that network's `inventoryWallet`, and keep encrypted files outside Git. Never send private keys, seed phrases, keystore files, or passphrases in chat or GitHub.

The operator's custody policy requires four different inventory wallet addresses. When `featureEnabled=true`, startup now rejects a missing wallet or any duplicate address before constructing payout adapters. This is deliberate: Ethereum and SOBYA are separate inventory roles even though both use EVM address formats. Keep all four networks disabled until the addresses, keystores, RPC chain identities, token balances, and native fee balances have been independently verified.

## Before enabling real payouts

Do not enable `featureEnabled` or any network flag until the full coordinator/API and deposit-watcher processes are deployed and supervised, the exact inventory addresses and chain IDs are verified, RPC endpoints respond correctly, encrypted keystores and passphrases are installed as environment/runtime secrets, fee balances and inventory are verified, and an end-to-end controlled test passes.

The example config is a template, not production configuration. The payout worker is invoked only after the deposit queue has been processed in each cycle; it can therefore see a newly finalized deposit in the same cycle. The quote provider keeps the agreed base reference price at 0.005 USDT per SOBY. It reads the native SOBY balance directly from the configured SOBYA HTTPS RPC at a finalized block for every quote, verifies chain ID and freshness, and derives pricing reference depth from spendable live SOBY inventory at the base price. No external USDT liquidity deposit, copied inventory balance, or manual demand snapshot is needed. Demand uses only completed ledger orders after both deposit and payout finality. Upward demand sensitivity is four times downward sensitivity by default: price rises faster than it falls. There is deliberately no upper price ceiling. The approved per-order cap is 500 USDT, the per-network daily cap is 10,000 USDT, and the fee is 1% (100 bps). The approved protected minimum is 100,000 SOBY (100000000000000000000000 base units); this amount remains protected inside the existing SOBYA inventory wallet, is not a separate wallet or extra deposit, and missing or stale reserve settings fail closed. Do not enable live payouts with null or guessed risk settings.



### Pricing and limit units

- `baseReferencePriceUsdtPerSoby` is decimal USDT per 1 SOBY and remains `0.005` as the agreed starting reference.
- USDT order/daily limits use 6-decimal USDT base units. Pricing depth is derived from live spendable SOBY inventory; there is no configured upper price ceiling.
- `minimumInventoryBaseUnits` and `verifiedPayoutInventoryBaseUnits` use 18-decimal SOBY base units. The approved `minimumInventoryBaseUnits` is 100,000 SOBY.
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
