# SOBYA Custodial Inventory Swap

This is the selected initial product model, replacing the earlier per-order escrow and solver design.

## User flows

- USDT to SOBY: select Ethereum, TRON, or Solana; receive a unique deposit destination for the order; the watcher verifies the correct USDT asset, amount, recipient, transaction success, and finality; the service checks the quoted SOBY amount against available inventory; a local payout worker sends native SOBY to the user's SOBYA wallet.
- SOBY to USDT: receive a unique SOBYA deposit destination/order; after finality, the payout worker sends USDT from the selected Ethereum, TRON, or Solana inventory wallet to the user's destination address.

The platform is custodial: project-controlled wallets hold the assets. This avoids source-chain escrow contracts and a solver marketplace, but users must be told that custody and payout availability depend on the platform's wallets and controls.

## Required automation

1. Allocate a unique deposit address per order, or a chain-native unique memo where supported. A single shared address without a unique identifier cannot safely attribute concurrent deposits.
2. Watch finalized transactions using SOBYA-operated node infrastructure for Ethereum, TRON, Solana, and SOBYA.
3. Record each source event once. A network/transaction/event tuple can fund at most one order.
4. Lock the quote in integer base units, apply fees and limits, and check inventory before accepting an order.
5. Send payouts from the corresponding inventory wallet using local encrypted key custody. Private keys must never enter the browser, repository, API request, or logs.
6. Reconcile wallet balances against the order ledger and pause new orders if a watcher is stale, liquidity is low, or a payout is unresolved.

## Order lifecycle

CREATED -> DEPOSIT_SEEN -> DEPOSIT_FINAL -> PAYOUT_SUBMITTED -> COMPLETE

No payout can be submitted before positive finalized-deposit verification. Replayed deposit events are rejected. Payout retries must inspect the original transaction before replacement; they must never blindly create a second payment.

## Implementation boundary

The custodial ledger module is the order-state core. It does not itself connect to RPCs, hold keys, sign, or broadcast. Chain-specific watchers and payout adapters must be connected and tested before enabling deposits. The sample deployment remains disabled until the four inventory wallet addresses, exact USDT contract/mint identities, node endpoints, and local keystore paths are configured.

This model does not require source-chain escrow contracts, an attestor quorum, a solver marketplace, or separate bridge deployments. It still requires project-operated chain connectivity and secure signing.
