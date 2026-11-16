# SOBYA BUY

A separate purchase portal for buying native SOBY. Initial intended payment choices:

- USDT on Ethereum mainnet
- ETH on Ethereum mainnet
- BNB on BNB Smart Chain
- Native SOL on Solana mainnet (MetaMask Connect Solana wallet)

The current page supports MetaMask EVM connection and a separate MetaMask Connect Solana payment-wallet connection. The Solana payment address is distinct from the EVM SOBYA receiving address. The purchase action is deliberately disabled until the payment verifier and secure SOBY payout service are configured and tested.

## Approved opening price policy

- **Opening reference price:** USD 0.005 per SOBY.
- **Quote validity target:** 10 minutes (600 seconds).
- **Dynamic pricing direction:** increase more noticeably as verified purchase demand rises and sale inventory falls; decrease more slowly and by a smaller amount when demand cools.
- The USD 0.005 value is an approved planning/reference price only. It is not yet a live executable quote or a claim about the market price.
- Dynamic quotes are not active until a backend implements and tests the pricing rules. Do not enable purchases based only on this public configuration.

At the reference price, 1,000,000 SOBY would correspond to USD 5,000 in gross quoted sale value before fees, slippage, discounts, or any future price changes. This is not guaranteed revenue or a market valuation.

## Wallet roles

- **Project payment receiving wallet (Ethereum / BNB Chain):** `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`
- **SOBYA BUY Reserve inventory wallet (SOBYA EVM):** `0xebdb899fFE84a89e1d576964b640491c135651AD`

The owner has allocated an opening inventory of **1,000,000 SOBY** to the reserve wallet. Confirm the on-chain balance before enabling sales. The reserve address is public configuration only. Its private key and recovery phrase must remain under the owner's control and must never be committed to GitHub or entered into the website.

## Security architecture

GitHub Pages is a static host. Never put a private key, seed phrase, RPC credential, or payout signer secret in this repository or browser code. The browser must not be trusted to prove a payment happened.

The production flow must be:

1. Browser requests a time-limited quote/order from a server-side API.
2. User sends the exact payment asset from MetaMask to the project's verified receiving address on the selected chain.
3. Server independently verifies chain ID, token contract (for USDT), recipient, amount, transaction status, confirmation depth, and unique transaction hash.
4. Server records the transaction hash as consumed before issuing any payout (idempotency and replay protection).
5. A server-side SOBYA signer sends the quoted native SOBY amount to the buyer's SOBYA EVM address.
6. The order API returns the payout transaction hash and status.

The SOBYA payout private key must be held only as a server-side secret, never in this repository or browser code. Prefer a controlled signing service or isolated signer with strict spending limits, transaction logging, and an emergency pause.

## Current stage

This is the UI and wallet-connect scaffold only. The public configuration contains the two public wallet addresses, the approved opening reference price, and the intended quote policy. However, `paymentsEnabled` remains `false`, `apiBaseUrl` is empty, automatic quotes are disabled, and the payment verifier and payout API are not deployed. No funds can be collected and no SOBY can be dispensed from this page yet.

## Required before real purchases

- Verify the reserve address and its SOBYA network/account mapping and confirm its current balance.
- Implement and test the asymmetric dynamic quote policy and enforce the 10-minute quote expiry server-side.
- Set up a server-side API and secure SOBYA payout signer, with its key stored only in a secure hosting secret store or isolated signing system.
- Keep sufficient native SOBY in the reserve wallet for network fees, separately accounting for sale inventory.
- Verify official chain RPCs and payment token contracts; start with USDT on Ethereum, ETH on Ethereum, native BNB on BNB Smart Chain, and native SOL on Solana mainnet. Solana signature verification, finalized commitment handling, and SOL/USD conversion must be implemented and tested before enabling that payment rail.
- Add order limits, minimum confirmations, duplicate-payment protection, audit logs, and an operator pause switch.
- Test in a controlled environment before enabling production payments.

## Hosting

The root website's GitHub Pages workflow publishes the repository root. After merging and a successful Pages deployment, this page will be available at /buy/.

No chain software upgrade, genesis reset, or DEX liquidity pool is required for this static interface. Production automatic payouts do require a separate backend service and an operational SOBYA RPC connection.
