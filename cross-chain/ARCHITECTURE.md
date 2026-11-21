# SOBYA Cross-Chain Swap Architecture

Status: design baseline only; not production code and not deployed.

## 1. User experience

The SOBYA DEX will expose two modes under one interface:

- **Local Swap** — executes against SOBYA AMM pools.
- **Cross-Chain Swap** — accepts USDT from TRON, Ethereum, or Solana and delivers SOBY to a SOBYA address.

The UI must never imply that a quote is executable unless a live solver has reserved sufficient SOBY inventory and the relevant source escrow/verifier contracts are active.

## 2. Why intent-based settlement first

A Solidity AMM pair on SOBYA cannot read USDT balances or transactions on TRON, Ethereum, or Solana. A traditional wrapped-asset bridge would require locking source USDT and minting a distinct wrapped representation on SOBYA. The agreed initial direction is instead a cross-chain swap intent: the source payment and destination SOBY payout are linked by a unique order, without pretending source USDT is already an ERC-20 on SOBYA.

This is a solver/settlement model, not a magic direct connection between chains. A solver must have SOBY available for payout on SOBYA and must receive the source USDT only after the payout condition is satisfied. Solver inventory must be reserved before quoting. A SOBYA-operated initial solver is possible, but it concentrates inventory and operational risk; the DEX must disclose that concentration and enforce strict caps.

## 3. Components

### DEX frontend

Creates an order request, displays a signed quote, asks the user's wallet to submit the source-chain deposit, tracks order state, and displays the SOBYA payout transaction. It must show source network, source USDT contract/mint, amount, destination SOBYA address, fees, quote expiry, finality policy, and refund deadline.

### Quote and order service

Produces a deterministic order payload and obtains solver commitments. The service is not trusted to custody funds or declare a deposit valid. Quote IDs are unique and expire. All security-critical fields are committed in the signed order.

### Source-chain escrow

A separate escrow implementation per source chain:
- TRON: TVM-compatible contract.
- Ethereum: EVM contract.
- Solana: Solana program.

The escrow holds only the exact USDT amount for an order. It has no arbitrary owner withdrawal. State transitions must be explicit and terminal states mutually exclusive.

### Verification and relaying

SOBYA-operated observers verify source-chain deposit finality and SOBYA payout finality using SOBYA-operated chain nodes. Under the selected no-third-party operating constraint, the attestor threshold is also controlled by SOBYA and is therefore a single-operator trust model. Separate processes, hosts and keys provide fault containment, not independent governance. A threshold signature is not a light client and must not be described as trustless. See [self-hosted operations](SELF_HOSTED_OPERATIONS.md).

A later trust-minimized design may replace or supplement attestations with chain-specific light-client proofs where feasible.

### SOBYA settlement

The destination settlement component validates the committed order and payout authorization, prevents replay, and records completion. It must not mint arbitrary native SOBY. The payout asset is native SOBY transferred from a funded solver inventory or explicitly governed reserve. The design must define who pays gas and how failed payouts are retried without double payment.

## 4. Order state machine

Conceptual states:

`QUOTED -> COMMITTED -> SOURCE_FUNDED -> SOURCE_FINAL -> DESTINATION_PAID -> COMPLETE`

Alternative terminal paths:

- `QUOTED/COMMITTED -> EXPIRED` when no source deposit was made before quote expiry.
- `SOURCE_FUNDED/SOURCE_FINAL -> REFUNDABLE -> REFUNDED` if no valid destination payout occurs before the refund deadline.
- `DESTINATION_PAID -> COMPLETE` only after payout confirmation; the source escrow claim then becomes available to the committed solver under the order's exact rules.

The implementation must resolve race conditions between payout and refund on-chain. Solver claim must execute before the refund deadline; after that deadline a late attestation cannot authorize a solver claim, and the user refund path remains available. No off-chain status update alone can make a terminal transition valid.

## 5. Atomicity and solvency limitation

The three chains do not share one atomic transaction. The system therefore cannot promise unconditional atomic swaps without a cryptographic protocol and suitable chain support. The initial design uses escrow, deadlines, proof/attestation, and explicit refund paths. This introduces trust and liveness assumptions that must be documented.

A solver needs sufficient SOBY inventory before quoting. The service must reject or pause quotes when inventory is insufficient. It must not use one user's USDT deposit as a guarantee to pay unrelated earlier users. No unlimited redemption promise is permitted.

## 6. Relationship to SOBY/USDT AMM liquidity

Cross-chain source escrow and the SOBYA AMM pool are separate systems:

- USDT deposited on TRON/Ethereum/Solana remains in that source-chain order escrow until the defined solver claim or refund transition.
- It does not become a token balance in a SOBYA pair.
- A local SOBY/USDT AMM pool requires a real, explicitly identified USDT representation on SOBYA and both assets funded on SOBYA.
- If the project does not want wrapped USDT, the cross-chain intent route can still deliver SOBY, but it does not create a local SOBY/USDT market.

The requested liquidity protection must distinguish project-owned LP positions from user LP positions. The project must not have an unrestricted admin path to withdraw pool assets. User LP redemption rights must be explicit; permanently trapping all user LP tokens is not an acceptable default.

## 7. Chain-specific finality

- Ethereum: require the selected finality threshold and handle reorgs before accepting a deposit proof.
- TRON: require the network's solidified/finalized block semantics and validate the expected USDT contract and event fields.
- Solana: require finalized commitment, verify the expected token program and USDT mint, token account owner, amount, transaction status, and instruction path. Reject processed/confirmed-only observations if the configured policy requires finalized.

The exact USDT contract/mint addresses, decimals, token program, escrow addresses, and finality parameters must be sourced and reviewed before any chain is enabled. They are intentionally absent from the example config.

## 8. Required interfaces before implementation

- `QuoteProvider`: returns a signed, expiring quote and solver reservation.
- `OrderRepository`: idempotent order state persistence.
- `SourceChainAdapter`: chain-specific deposit construction and finalized proof verification.
- `SettlementAdapter`: verifies SOBYA payout and drives safe state transitions.
- `Solver`: reserves SOBY inventory, executes payout, and claims source escrow only under the contract rules.
- `RiskController`: global/per-chain limits, pause controls, inventory thresholds, anomaly detection, and incident procedures.

The native-SOBY destination payout contract prototype is implemented under `contracts/src/SobyaCrossChainSettlement.sol`; it emits a payout event but does not verify source-chain deposits itself. Read-only Python observers now verify Ethereum escrow funding at the finalized block tag and SOBYA payout receipts/events using mocked-RPC tests. They do not sign attestations or submit transactions. TRON/Solana source observers, self-hosted node operations, a local observer supervisor, signer processes, durable order API, solver inventory service, and risk controller remain outstanding.
