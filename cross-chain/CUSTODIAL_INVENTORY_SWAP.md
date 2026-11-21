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

The quote pricer can adjust the operator-published base reference rate using only finalized, executed swap volume over a rolling one-hour window. Net USDT demand for SOBY raises the quoted USDT-per-SOBY rate; net SOBY sales lower it. Pending quotes, unfinalized deposits, cancelled orders, and failed payouts are not demand.

The adjustment is bounded by configuration (example ceiling: +/- 15%). A stale, unavailable, mismatched-window, or non-finalized demand snapshot causes quote creation to fail closed rather than silently using stale market pressure. The configured base rate remains an explicit economic policy input; the demand formula does not invent a starting market price or guarantee a market value.

The production adapter must supply authenticated, deduplicated, finalized executed volume from the custodial order ledger. This change adds the bounded calculation and quote-pricer hook; it does not claim that the production volume aggregator or all chain watchers are already deployed.
