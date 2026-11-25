# SOBYA Auto Exchange (isolated)

Independent project under `auto-exchange/`. It does not modify `buy/`, `dex/`, existing contracts, chain configuration, or live balances.

## Wallet and networks
- Inventory EVM address: `0xebdb899fFE84a89e1d576964b640491c135651AD`.
- Ethereum mainnet (chain ID 1): customer USDT deposit network.
- SOBYA EVM (chain ID 357812033857): SOBY payout network.
- Verified primary SOBYA EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`.
- Previous NodeSafe hostname `https://sobya-evm-rpc.nodesafe-app.xyz` is retained only as a read-only verifier fallback; it is not the selected primary.
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

## Reverse SOBY-return / USDT-refund flow
- Customers submit a separate GitHub Issue using `.github/ISSUE_TEMPLATE/auto-exchange-return.yml`.
- The return quote reserves a unique exact SOBY atomic amount, fixes the refund price for ten minutes, and calculates the USDT refund after the same 1% fee.
- The return worker scans confirmed native SOBY transfers to the inventory wallet on SOBYA EVM, matching exact sender, recipient, amount, chain, quote window, and transaction replay key.
- After two SOBYA confirmations, the worker checks USDT inventory and the separate Ethereum ETH gas reserve, reserves the Ethereum nonce in the GitHub ledger, and sends the quoted USDT refund.
- It marks the return settled and applies the 25-bps downward price movement only after 12 Ethereum confirmations and an exact USDT `Transfer` event from the inventory wallet to the customer's quoted address.
- The return quote and refund workflows use GitHub Issues, GitHub Actions, and the same committed JSON ledger; they do not require a separate server.

## Security state — no live funds
- `tradingEnabled: false`.
- `payoutEnabled: false`.
- Both flags remain false by default. The payout and refund workers exit before accessing RPC credentials or the signing key while either flag is false.
- The verified SOBYA RPC endpoint is a read-only connectivity result; it does not establish that signing, broadcasting, gas estimation, or transaction inclusion works.
- The payout worker is implemented but is not authorized for live use until the PR is reviewed and merged, GitHub Actions secrets are configured, and controlled end-to-end tests have passed. Do not send USDT or SOBY while disabled.
- Required repository Actions secrets after review: `ETHEREUM_RPC_URL`, `SOBYA_EVM_RPC_URL`, and `SOBYA_PAYOUT_PRIVATE_KEY`. Set `SOBYA_EVM_RPC_URL` to the verified primary endpoint above. Never put the private key in an issue, chat, source file, or workflow output. The key must derive the configured inventory address.
- Ethereum USDT deposits are matched by exact sender, destination, token, amount, chain, quote validity, 12 confirmations, and transaction-log replay key.
- SOBY payouts wait for 2 SOBYA confirmations. Before broadcast, the worker estimates gas and requires the payout amount plus a 20% buffered gas reserve.
- A successful confirmed SOBY payout records the receipt and applies the upward price movement once to the persisted ledger.
- The reverse return worker and issue workflow are implemented in this branch, but both are also gated by the same disabled policy flags. No USDT refund can execute while either flag is false.
- If execution stops after a payout nonce is durably reserved or a transaction is broadcast, the order is held for manual reconciliation and is not blindly resent.
- No private key is placed in frontend files, Git history, or workflow logs. The quote workflow handles untrusted issue text without wallet secrets.
- No paid contract, paid hosting, or new paid service is part of this design.

## Tests
Run `npm test` inside `auto-exchange/`. GitHub Actions tests cover quote allocation, settlement matching, pricing, payout gas-reserve and mocked payout lifecycle, SOBY-return matching, and mocked USDT-refund lifecycle. These deterministic tests do not verify live transaction execution or authorize real-money operation.
