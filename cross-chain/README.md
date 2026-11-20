# SOBYA Cross-Chain Swap

This directory defines the first engineering milestone for integrating cross-chain swaps into the existing SOBYA DEX.

## Scope

The planned user flow is one DEX experience:

- Local Swap: trades against pools deployed on SOBYA.
- Cross-Chain Swap: a user pays USDT on TRON, Ethereum, or Solana and receives native SOBY on SOBYA after the source payment is finalized and independently verified.

This is **not** a claim that a bridge, source-chain escrow, solver network, or cross-chain swap is deployed. The initial configuration is deliberately disabled. No production transaction can be initiated from this work.

## Chosen initial model: intent-based settlement

The initial design is a non-wrapped-token, intent-based swap:

1. The user requests a quote for a fixed amount of USDT on one supported source chain and a SOBY destination address on SOBYA.
2. A solver (or a decentralized solver set) commits to the quote and provides the SOBY payout inventory on SOBYA.
3. The user deposits USDT into a source-chain escrow contract for that specific order.
4. Independent verification confirms the source-chain deposit reached the required finality.
5. The solver pays SOBY to the destination address on SOBYA.
6. The order is marked complete only after the SOBYA payout is confirmed. The solver's claim to the source USDT is governed by the order state machine and the source escrow contract.
7. If the order expires without a valid payout, the user can reclaim the escrowed USDT under the documented refund rules.

This model avoids representing bridged USDT as an ordinary ERC-20 on SOBYA. It also keeps source-chain USDT separate from any future SOBY/USDT AMM pool on SOBYA. A local AMM pair still needs a real USDT representation deployed on SOBYA and funded independently.

## Chain adapters

- TRON: source escrow and event/finality adapter for TRON's finalized/solidified blocks.
- Ethereum: source escrow and event/finality adapter for Ethereum finality and reorg handling.
- Solana: source escrow program and adapter using finalized commitment, signature/status verification, and replay protection.

Each adapter must produce the same normalized deposit proof fields while retaining chain-specific proof validation.

## Security invariants

- No source USDT is released to a solver before a valid SOBYA payout is proven.
- A source deposit can be consumed by exactly one order.
- Chain ID, escrow address, order ID, recipient, amount, asset mint/contract, and expiry are bound into the order.
- Duplicate, replayed, malformed, non-final, or reorged deposits cannot create a payout.
- User refunds and solver claims are mutually exclusive terminal outcomes.
- Pausing new orders must not silently confiscate funds or disable a safe, already-earned refund path.
- No single project-controlled key can mint arbitrary SOBY, release escrow, or bypass verification.
- Quotes must disclose fees, slippage/price expiry, solver, expected finality, and refund conditions.

## Implementation sequence

1. Architecture, state machine, threat model, and disabled chain registry (this milestone).
2. Local deterministic test harness and order-state model; no real funds.
3. Source-chain escrow prototypes on TRON, Ethereum, and Solana testnets.
4. SOBYA payout/settlement contract prototype and independent verifier/relayer interfaces.
5. Adversarial tests, reorg/finality tests, replay tests, refund tests, and external security review.
6. DEX UI integration behind a hard-disabled feature flag.
7. Testnet end-to-end operation with independent operators.
8. Mainnet deployment only after explicit approval, funded solver inventory, verified addresses, audit, and controlled live tests.

## Explicit non-goals for this milestone

- No mainnet deployment or transaction.
- No activation of DEX swaps.
- No creation or minting of a USDT-like token on SOBYA.
- No claim that source-chain USDT is AMM liquidity on SOBYA.
- No admin withdrawal function for user escrow.
- No promise of zero operating cost: source-chain gas, relayer/solver operations, monitoring, and audits remain necessary.

See [architecture](ARCHITECTURE.md), [threat model](THREAT_MODEL.md), and [disabled network registry](config.example.json).
