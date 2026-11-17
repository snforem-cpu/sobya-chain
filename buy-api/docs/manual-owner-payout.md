# SOBYA BUY — manual owner-approved payout design

## Status

This document is an implementation specification only. It does not enable sales, create payment addresses, verify payments, or send SOBY. The Worker must remain fail-closed and `SALE_ENABLED=false`.

## Fixed inventory source

The owner-approved SOBYA inventory wallet is:

`0xebdb899fFE84a89e1d576964b640491c135651AD`

Do not replace this address, create a second inventory wallet, or request another inventory deposit. Never put its private key or recovery phrase in GitHub, Cloudflare Worker variables, browser code, logs, or support messages.

## Required customer flow

1. The API issues a short-lived quote with a server-generated ID, buyer receiving address, exact SOBY amount in integer base units, payment asset/network, exact payment amount, and expiry.
2. Payment verification is performed server-side against the correct chain. The API independently validates the transaction recipient, asset contract (where applicable), amount, sender/buyer binding, chain ID, successful receipt/finality, and replay protection. A browser-supplied “paid” flag is never evidence.
3. A payment is recorded as `verified` only after the configured confirmation/finality policy is met. Reorgs and replaced transactions must be handled before payout eligibility.
4. The owner opens a protected owner console and signs a fresh, one-time server challenge with the approved wallet. The server verifies the signature, nonce, expiry, domain/origin and recovered address. The only authorized owner is the fixed inventory wallet above.
5. The console lists only verified, unpaid orders. Each row shows the order ID, buyer receiving address, exact SOBY amount, payment asset/network, verified payment transaction, and quote details. The browser cannot alter the payout destination or amount.
6. On owner approval, the browser requests a transaction from MetaMask on SOBYA Mainnet (EVM chain ID `357812033857`). The transaction is constructed from the server-validated order and sent by the fixed inventory wallet. The owner reviews and signs each transfer in MetaMask.
7. The API accepts a payout transaction hash only after verifying on the SOBYA RPC that the transaction was sent by the fixed inventory wallet, transfers the exact approved amount to the approved buyer address, succeeded, and reached the configured finality threshold.
8. Only then is the order marked paid, the inventory reduced atomically, the price policy updated from verified completed sales, and an append-only audit event written.

## Concurrency and replay safety

- Enforce a unique payment transaction hash per payment chain and a unique payout transaction hash.
- Use an atomic compare-and-set state transition such as `verified -> payout_pending` before displaying/approving a payout. Reject a second approval while one is pending.
- Bind the approval to an immutable order version and server-generated idempotency key.
- Never decrement inventory or increase verified demand when a quote is created, payment is merely detected, or a payout is merely requested.
- Reconcile uncertain transactions before allowing retry. A timeout is not proof of failure.
- Reject expired quotes and payments with mismatched asset, chain, recipient, amount, or buyer.
- Do not allow the client to submit arbitrary payout token contracts, amounts, destinations, or chain IDs.

## Notifications

The owner console may show pending-order alerts while open. Browser notifications require explicit permission and may not arrive when the page is closed. Background push or Telegram/email alerts require a separately configured delivery integration; do not claim those exist until tested.

## Required completion gates

Before sales can be enabled, implement and test all supported payment rails (ETH and USDT on Ethereum, BNB on BNB Chain, and SOL on Solana), independent transaction verification and finality/reorg handling, quote expiry, atomic inventory reservation/reconciliation, owner challenge authentication, manual MetaMask payout construction, payout receipt verification, replay/concurrency protection, rate limits, audit logging, monitoring, and end-to-end tests.

The current repository has no production payment-verification or payout endpoints. Keep all commerce endpoints returning HTTP 503 and keep `SALE_ENABLED=false` until every gate above is implemented and independently tested.
