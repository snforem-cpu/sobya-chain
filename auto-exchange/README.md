# SOBYA Auto Exchange (isolated)

Independent project under `auto-exchange/`. It does not modify `buy/`, `dex/`, existing contracts, chain configuration, or live balances.

## Wallet and networks
- Inventory EVM address: `0xebdb899fFE84a89e1d576964b640491c135651AD`.
- Ethereum mainnet (chain ID 1): customer USDT deposit network.
- SOBYA EVM (chain ID 357812033857): SOBY payout network.
- The same EVM address is used on both chains; balances and transactions are separate.

## Recorded commercial policy
- Opening price: 0.005 USDT per SOBY.
- Reference inventory: 1,000,000 SOBY (not a claim about current wallet balance).
- Exchange fee: 1% (100 bps).
- Directional coefficients: 100 upward / 25 downward (4:1).
- Coefficients are basis points (BPS), scaled by trade quantity relative to the 1,000,000 SOBY reference inventory.
- Quote validity: 10 minutes.
- No fixed maximum price; time alone does not move price.
- A price change is permitted only after the corresponding trade/stock return is confirmed and settled.

## Dynamic price formula

Let P be the current price in USDT/SOBY and Q the confirmed quantity in SOBY:

- After a confirmed SOBY sale: `Pnew = Pold × (1 + 100/10000 × Q/1,000,000)`.
- After a confirmed SOBY stock return: `Pnew = Pold × (1 - 25/10000 × Q/1,000,000)`.

All calculations use integer fixed-point arithmetic (18 decimal places), not JavaScript floating-point math. The upward coefficient is four times the downward coefficient. Example for 10,000 SOBY: sale increases price by 0.01%; stock return decreases it by 0.0025%. Price never changes merely because time passes.

The pure price engine is in `pricing.js`. New quotes read `ledger.currentPriceUsdtPerSoby`, falling back to the opening price until a confirmed price update is recorded. Existing quotes retain their original `quotedPrice` and payout amount for their full ten-minute validity.

## Durable quote requests and unique payment amounts
- Customers submit a GitHub Issue using `.github/ISSUE_TEMPLATE/auto-exchange-quote.yml`.
- GitHub Actions scans all open quote-request issues on each event and every five minutes.
- The workflow uses one concurrency group and a single writer to update `auto-exchange/ledger.json`.
- Issue number is the idempotency key: reprocessing the same issue cannot create a second quote.
- Each quote reserves a globally unused exact USDT atomic-unit amount. The small micro-USDT routing tail is included in the displayed quoted total; it is not a separate fee.
- Amounts remain reserved in the ledger even after expiry, so a late payment can never accidentally match a later customer's quote.
- Quotes are created with a ten-minute expiry starting when the worker actually issues the quote, not when the customer first opened the request.
- If an event run is coalesced or delayed, the scheduled full-queue scan recovers open requests. Failed ledger writes fail the workflow and leave the issue pending for retry.
- Quote notifications are idempotent using an order-specific marker in the issue comments.

The issue queue and committed JSON ledger are durable GitHub records. This is not a continuously available API: issuance waits for GitHub Actions and scheduled runs can be delayed. Customers must not assume instant quotes.

## Deposit matching core
`settlement.js` checks Ethereum chain ID, sender, deposit address, USDT contract, exact atomic amount, one unique open quote, quote validity, confirmation threshold, and transaction-hash/log-index replay protection. It returns `matched_paid_not_settled`; it does not sign or send SOBY.

## Security state — no live funds
- `tradingEnabled: false`.
- `payoutEnabled: false`.
- The quote ledger is operationally a reservation/quote record only. No USDT deposit should be sent.
- No private key, signing secret, live RPC signer, or automatic payout code is present.
- No private key is placed in frontend files, Git history, or workflow logs.
- The quote workflow handles untrusted issue text but has no wallet secret and only creates validated quote records/comments.
- No paid contract, paid hosting, or new paid service is part of this design.

## Tests
Run `npm test` inside `auto-exchange/`. The test workflow runs the isolated policy, quote allocation, settlement, and price-movement tests.
