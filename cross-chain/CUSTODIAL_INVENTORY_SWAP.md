# SOBYA Custodial Inventory Swap

The selected model is custodial inventory: one inventory wallet per supported network, automatic finalized-deposit detection, and payout from project inventory. No per-order escrow contracts or solver marketplace are required.

## User flows

- USDT to SOBY: select Ethereum, TRON, or Solana; bind the submitted transaction hash/signature and token event index to the order; verify asset, amount, recipient, success, and finality; check SOBY inventory; pay the user on SOBYA.
- SOBY to USDT: deposit SOBY to the SOBYA inventory; after finality, pay USDT from the selected external-chain inventory wallet.

The platform is custodial. Users must be informed that assets are held by project-controlled wallets and payout depends on available inventory and operational controls.

## Automation and safety

1. Bind each order to the exact transaction hash/signature and event index.
2. Watch finalized transactions using project-operated node infrastructure.
3. Credit each source event once.
4. Lock quotes in integer base units, apply fees and limits, and verify payout inventory.
5. Sign and broadcast payouts using local encrypted key custody. Never expose private keys in browser, repository, API requests, or logs.
6. Reconcile balances and pause orders if watchers are stale, liquidity is low, or a payout is unresolved.

Order lifecycle: CREATED -> DEPOSIT_SEEN -> DEPOSIT_FINAL -> PAYOUT_SUBMITTED -> COMPLETE. No payout before finalized-deposit verification; retries must inspect the original payout to prevent duplicate payment.

## Demand-based SOBY reference pricing

- Initial reference rate: 0.005 USDT per SOBY, matching the current manual selling reference.
- Only net finalized executed swap volume changes price. Elapsed time alone never changes it; the time window only measures flow and rejects stale snapshots.
- Net USDT-to-SOBY buy flow raises price using a stronger coefficient. Net SOBY-to-USDT sell flow lowers it using a weaker coefficient.
- Exponential impact model: base price multiplied by exp(sensitivity multiplied by net flow divided by verified reference liquidity). Upward sensitivity defaults to 10000 bps; downward sensitivity defaults to 2500 bps.
- No configured price ceiling or floor. The model can calculate values above 100 or 1000 dollars if sufficient net executed demand supports them. This does not guarantee executable market value: real inventory and liquidity must support payouts at quoted prices.
- Reference liquidity is intentionally unset in the sample. It must be derived from verified, executable SOBY inventory valued at the 0.005 dollar reference rate; never guess it. Without it, quote calculation fails closed.
- Count only finalized, deduplicated completed swaps. Exclude pending deposits, quotes, cancelled orders, failed payouts, replayed events, and wash trading.

The pricing module is a calculation component, not a live oracle, quote endpoint, or production volume aggregator. A production adapter must build authenticated snapshots from finalized ledger events and connect the calculation to the quote API and DEX UI. Watchers, reconciliation, local signing, payout broadcasters, and end-to-end tests remain required. All networks stay disabled until completed and tested.

## Implementation status (2026-11-21)

- The SQLite order ledger and asymmetric demand-pricing calculation have unit tests.
- The new `custodial/inventory_deposit_watchers.py` module adds read-only direct-inventory deposit verifiers for all four selected networks:
  - Ethereum: ERC-20 Transfer log, exact token contract, sender, inventory wallet, amount, receipt success, canonical block hash, and finalized block height.
  - TRON: TRC-20 Transfer log from the Solidity Node, exact contract/sender/inventory/amount, successful receipt, and solidified block identity.
  - Solana: finalized SPL Token transfer instruction, exact signature and instruction index, sender authority, configured USDT mint, amount, and destination token-account mint/owner.
  - SOBYA: native EVM transfer, exact chain ID, sender, inventory recipient, amount, successful receipt, canonical block, and finalized height.
- `InventoryDepositRecorder` passes verified evidence into the existing SQLite ledger. The ledger's unique (network, transaction, event-index) constraint prevents replaying one chain event into multiple orders, and its exact asset/amount/recipient checks remain in force.
- Unit tests and a dedicated GitHub Actions workflow have been added for the new verifier module. Their CI result must pass before this work can be marked complete.
- These are transaction verifiers, not yet autonomous continuous scanners. The API/order service must accept an order-bound transaction ID/signature and event index, invoke the configured verifier, then persist the result. A background scanner/reconciliation loop, production RPC configuration, official asset-identity verification, and live-chain integration tests remain release requirements.
- The example config intentionally leaves every network and the feature disabled. No user deposits should be accepted and no payouts should be promised until the API integration, watcher liveness/restart recovery, and all release gates pass.

## Supplied inventory wallet addresses

The operator supplied these public receiving addresses for the inventory configuration:

- Ethereum mainnet: `0xebdb899fFE84a89e1d576964b640491c135651AD`
- TRON mainnet: `TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx`
- Solana mainnet-beta: `BMH7LJjaKkQRZd9EL4UqUfsTYEC44ZZoWSEdL1XWaSnh`
- SOBYA mainnet: `0xebdb899fFE84a89e1d576964b640491c135651AD`

The Ethereum and SOBYA entries intentionally use the same EVM address, but are separate balances on separate chains. These public addresses are recorded in the example configuration only; all network flags remain disabled. The operator reports that the SOBYA wallet holds 1,000,000 SOBY; that balance has not yet been independently checked by this software. Do not treat a configured address as proof of custody or signing capability: the corresponding private keys must remain under the operator's secure local control and must never be committed to GitHub.
