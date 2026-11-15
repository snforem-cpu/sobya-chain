# SOBYA BUY

A separate purchase portal for buying native SOBY. Initial intended payment choices:

- USDT on Ethereum mainnet
- ETH on Ethereum mainnet
- BNB on BNB Smart Chain

The current page supports MetaMask connection and network selection. The purchase action is deliberately disabled until the payment verifier and secure SOBY payout service are configured and tested.

## Wallet roles

- **Project payment receiving wallet (Ethereum / BNB Chain):** `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`
- **SOBYA BUY Reserve inventory wallet (SOBYA EVM):** `0xebdb899fFE84a89e1d576964b640491c135651AD`

The reserve address is public configuration only. Its private key and recovery phrase must remain under the owner's control and must never be committed to GitHub or entered into the website. The reserve is intended to hold only the SOBY amount explicitly allocated for sale, transferred from the project's liquidity allocation when the owner approves it. No inventory transfer has been performed by this code change.

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

This is the UI and wallet-connect scaffold only. The public configuration contains the two public wallet addresses, but `paymentsEnabled` remains `false`, the dynamic pricing service and API are not deployed, and no inventory has been transferred. No funds can be collected and no SOBY can be dispensed from this page yet.

## Required before real purchases

- Verify the reserve address and its SOBYA network/account mapping before transferring inventory.
- Decide the initial reference price and implement the asymmetric dynamic quote policy (demand and remaining inventory).
- Set up a server-side API and secure SOBYA payout signer, with its key stored only in a secure hosting secret store or isolated signing system.
- Fund the reserve wallet with the SOBY inventory allocated for sale and enough native SOBY for network fees.
- Verify official chain RPCs and payment token contracts; start with USDT on Ethereum, ETH on Ethereum, and native BNB on BNB Smart Chain.
- Add order limits, quote expiry, minimum confirmations, duplicate-payment protection, audit logs, and an operator pause switch.
- Test in a controlled environment before enabling production payments.

## Hosting

The root website's GitHub Pages workflow publishes the repository root. After merging and a successful Pages deployment, this page will be available at /buy/.

No chain software upgrade, genesis reset, or DEX liquidity pool is required for this static interface. Production automatic payouts do require a separate backend service and an operational SOBYA RPC connection.
