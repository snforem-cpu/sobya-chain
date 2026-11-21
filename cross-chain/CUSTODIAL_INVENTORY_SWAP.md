# SOBYA Custodial Inventory Swap

This is the selected initial product model, replacing the earlier per-order escrow and solver design.

## User flows

- USDT to SOBY: select Ethereum, TRON, or Solana; the DEX sends USDT to that network's shared inventory wallet and binds the exact transaction hash/signature plus token event index to the order; the watcher verifies the correct USDT asset, amount, recipient, transaction success, and finality; the service checks the quoted SOBY amount against available inventory; a local payout worker sends native SOBY to the user's SOBYA wallet.
- SOBY to USDT: deposit SOBY to the dedicated SOBYA inventory wallet and the DEX binds the exact transaction hash to the order; after finality, the payout worker sends USDT from the selected Ethereum, TRON, or Solana inventory wallet to the user's destination address.

The platform is custodial: project-controlled wallets hold the assets. This avoids source-chain escrow contracts and a solver marketplace, but users must be told that custody and payout availability depend on the platform's wallets and controls.

## Required automation

1. Use one dedicated inventory address per network. The DEX must initiate the transfer from the connected wallet and bind the exact returned transaction hash/signature and token event index to the order. This safely attributes concurrent deposits to the same shared address. A transfer sent outside the DEX flow must be submitted with its transaction hash before it can be credited.
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

## Demand-responsive SOBY reference price

The operator-approved base reference rate is an explicit configuration input named baseReferencePriceUsdtPerSoby. It is deliberately unset in the example configuration; quote creation must fail closed until the project explicitly sets it. This prevents code from inventing a starting market price.

The new deterministic pricing module adjusts that base rate using finalized, executed swap volume over a rolling one-hour window, normalized to USDT base units:
- Net USDT -> SOBY buy pressure raises the USDT-per-SOBY quote.
- Net SOBY -> USDT sell pressure lowers it.
- Balanced flow leaves the base rate unchanged.
- The adjustment is capped at +/- 15% by default, with 20% sensitivity before the cap.
- Stale, future-dated, unfinalized, or wrong-window snapshots are rejected.

Only completed, finalized swaps may enter the demand snapshot. Quotes, pending deposits, cancelled orders, and failed payouts are not demand. The module has unit tests and is added to coordinator CI.

## Remaining integration boundary

The pricing module is a tested calculation component, not yet connected to the live quote endpoint or a production volume aggregator. A production adapter must build authenticated, deduplicated, finalized volume snapshots from the order ledger, then call this module before a quote is issued. The chain-specific watchers, inventory reconciliation, local signing, payout broadcasters, and DEX quote/UI integration also remain required. All networks stay disabled until those components and end-to-end tests are complete.
