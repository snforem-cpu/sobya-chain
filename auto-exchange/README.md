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
- Exchange fee: 1% (100 bps), separate from network fees.
- Network fees are charged to the customer by deducting the estimated network cost from the outgoing asset: SOBYA gas from the SOBY payout, and Ethereum gas converted to USDT using the fresh Chainlink ETH/USD mainnet feed from the USDT refund. The refund path fails closed if the feed is invalid or older than one hour.
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
- All four quote, payout, and refund workflows share one repository concurrency group, serializing every writer that updates `auto-exchange/ledger.json`.
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
- After two SOBYA confirmations, the worker estimates Ethereum gas, reads a fresh Chainlink ETH/USD mainnet price, converts the buffered gas cost into USDT atomic units, and deducts that network fee from the gross refund. It checks USDT inventory for the net amount and the separate ETH gas reserve, then reserves the Ethereum nonce in the GitHub ledger and sends the net USDT refund. If inventory or ETH gas is insufficient, the order remains in a retryable funding-wait state and resumes automatically on a later run after funds arrive; it does not reserve a nonce while waiting.
- It marks the return settled and applies the 25-bps downward price movement only after 12 Ethereum confirmations and an exact USDT `Transfer` event from the inventory wallet to the customer's quoted address.
- The return quote and refund workflows use GitHub Issues, GitHub Actions, and the same committed JSON ledger; they do not require a separate server.

## Operational activation state
- USDT → SOBY buying and automated SOBY payouts are enabled independently of the reverse direction.
- SOBY → USDT return quotes and refunds remain disabled until the inventory wallet has USDT for refunds and ETH for Ethereum gas. This allows initial USDT purchases to build the USDT inventory without accepting unfunded return obligations.
- A read-only GitHub Actions preflight verified that the configured signing key is present and derives the configured inventory address. It also verified Ethereum chain ID 1 and SOBYA EVM chain ID 357812033857.
- At the preflight, the inventory wallet held 1,000,000 native SOBY, 0 USDT, and 0 ETH. The zero Ethereum balances do not block receiving USDT for initial purchases or sending native SOBY on SOBYA; they do block the reverse USDT refund route.
- Customers must request a fresh quote and send only the exact USDT amount to the quoted Ethereum address before the 10-minute expiry. Never send USDT without a valid quote. The payout worker requires 12 Ethereum confirmations, exact token/sender/recipient/amount matching, and replay protection.
- SOBY payouts wait for 2 SOBYA confirmations. Before broadcast, the worker estimates gas, deducts the buffered SOBYA network-fee budget from the gross quoted SOBY payout, and requires the gross amount in the inventory wallet. The customer receives the net SOBY amount. A zero gas price is accepted for SOBYA because its RPC reports zero; negative fee values remain rejected.
- A successful confirmed SOBY payout records the receipt and applies the upward price movement once to the persisted ledger.
- The reverse return worker and return-quote processor exit before accessing RPC credentials or the signing key while their independent return gates are false.
- If execution stops after a payout/refund nonce is durably reserved or a transaction is broadcast, the order is held for manual reconciliation and is not blindly resent. Insufficient balances before nonce reservation are recorded as retryable funding-wait states.
- The private key is not placed in frontend files, Git history, or workflow output. The read-only preflight reports only whether its derived address matches; it never prints the key.
- No real-money end-to-end transfer has been performed yet; the first accepted purchase will be a live transaction. No paid contract, paid hosting, or new paid service is part of this design.

## Tests
Run `npm test` inside `auto-exchange/`. GitHub Actions tests cover quote allocation, settlement matching, pricing, payout gas-reserve and mocked payout lifecycle, SOBY-return matching, and mocked USDT-refund lifecycle. These deterministic tests do not verify live transaction execution or authorize real-money operation.
