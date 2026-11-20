# SOBYA self-hosted cross-chain operation

Status: proposed operating profile for the existing prototype. Nothing in this document enables a network or authorizes a deployment.

## Objective

Run the cross-chain swap infrastructure under SOBYA's own control without depending on hired observers, external attestors, hosted RPC subscriptions, or a third-party relayer service.

This is a **single-operator trust model**. The processes and keys are controlled by SOBYA. Splitting them across machines and operating-system identities improves fault containment, but it does not make the system decentralized or independent of SOBYA.

## Components under SOBYA control

1. **Self-hosted chain data nodes**
   - Ethereum: an execution client paired with a consensus client, synchronized to the required finality view.
   - TRON: FullNode plus SolidityNode, with solidified-block reads enabled.
   - Solana: a synchronized RPC-capable validator/node with transaction-history and finalized-account reads enabled.
   - SOBYA: a local RPC endpoint for the destination chain and payout receipt checks.

   These are nodes operated by SOBYA, not SaaS RPC subscriptions. Do not silently fall back to public RPC endpoints when a local node is unhealthy. If the local node cannot provide the required finalized evidence, pause that chain's new orders.

2. **Read-only observer processes**
   - One chain-specific observer per source network, plus the SOBYA payout observer.
   - Observers read from SOBYA-operated nodes, validate chain ID/genesis identity, token, escrow, order fields, finality and canonical state.
   - Observers have no signing keys and cannot submit transactions.

3. **SOBYA-controlled attestor processes**
   - The source escrow contracts/programs require their configured threshold of signatures.
   - The intended self-operated profile uses separately provisioned signing instances and distinct keys, all administered by SOBYA. No outside person is required to hold an attestor key.
   - Keep each key outside the repository and outside the observer process. Do not expose keys to the DEX browser or quote API.
   - An attestor signs only after it has independently queried the local chain data and verified the SOBYA payout against the complete order commitment.
   - The current prototype has no signer daemon, key provisioning, secure key store, or signing automation. These must be implemented and tested before any source escrow is enabled.

4. **Local coordinator and risk controller**
   - The coordinator stores immutable quotes and verified evidence.
   - The risk controller enforces per-order and global caps, solver inventory reservations, deadlines, rate limits, and chain-specific pause switches.
   - Coordinator state is not proof by itself. It may record evidence only after the observer checks succeed.

## Trust and security limits

- All attestor keys ultimately belong to one operator. A compromise of SOBYA's control plane, or collusion/access to the required number of keys, can authorize a false source-escrow claim. This model is **not trustless, not decentralized, and not equivalent to independent third-party attestors**.
- Multiple observer processes or URLs do not prove independent evidence when they use the same node, upstream, operator, or infrastructure.
- A local observer quorum can detect a faulty node only when its data sources are genuinely separate. Multiple self-hosted nodes still share SOBYA's administrative trust boundary.
- The system must never pay out based solely on an API response, database row, browser event, or one RPC response.
- Start with conservative caps and delayed settlement. If any node disagrees, falls behind, loses finality data, or becomes unavailable, fail closed and stop accepting new orders on that chain.
- A pause must not remove a user's already-earned refund right. Existing escrow refunds must remain callable under the source contract's deadline rules.

## No third-party service policy

- Do not require Alchemy, TronGrid, Helius, QuickNode, hosted relayers, external observer companies, or hired attestors for the self-hosted profile.
- Do not insert public RPC endpoints as production fallbacks.
- Public endpoints may be used only for explicitly labelled development experiments; they must not count as independent production attestations.
- If SOBYA cannot keep a source-chain node synchronized and available, keep that source chain disabled instead of claiming it is supported.

## Cost and availability reality

Self-hosting avoids mandatory SaaS subscriptions, but it is not costless by definition. The nodes require suitable hardware, disk space, bandwidth, electricity, maintenance and chain-specific synchronization time. Ethereum and Solana in particular can have substantial resource requirements. Existing hardware may reduce cash expense, but a free hosted service cannot be assumed to provide production-grade uptime or trust.

A chain is not ready merely because its observer code passes unit tests. Readiness requires the node to synchronize, pass live finality checks, and complete end-to-end tests on that chain's test network before any mainnet use.

## Implementation gates

1. Implemented: independent config/order PDA derivation and forged-PDA rejection tests in the Solana source observer. Still pending: validator-based integration tests.
2. Added a self-hosted node configuration template with public-RPC fallback disabled; all networks remain disabled and example identities must be pinned before use.
3. Added a fail-closed supervisor library and read-only probe adapters for Ethereum/SOBYA EVM, TRON FullNode+SolidityNode, and Solana JSON-RPC. The adapters check EVM chain ID/head/finalized tag/syncing, TRON genesis/head/solidified height, and Solana genesis/health/processed+finalized slots. They use bounded HTTP responses/timeouts and reject public RPC URLs. Mocked unit tests cover adapter behavior; no live-node connection or testnet integration has been performed. Current adapters use each node's own head as the reference height, so cross-node peer-head comparison is not yet supplied by the adapters. They do not independently verify consensus or act as light clients. The config-to-supervisor factory is implemented, but deployment and wiring into a running supervisor service remain pending.
4. Implement separately isolated SOBYA-controlled attestor processes and key lifecycle; keep all signing disabled by default.
5. Add coordinator/risk-controller integration, strict caps, pause and refund-preservation tests.
6. Run end-to-end tests on each source-chain test network and SOBYA test environment.
7. Review the single-operator trust model and publish it honestly in the DEX UI.
8. Enable any network only after explicit owner approval. No mainnet deployment, signing, escrow claim, or funds movement is authorized by this document.
