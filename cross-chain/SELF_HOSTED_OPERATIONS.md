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


## Local supervisor readiness service

A loopback-only operational service is now included at `cross-chain/observer/supervisor_service.py`. It loads the self-hosted JSON configuration, constructs the read-only chain probes and supervisor, and refreshes health on a fixed interval.

Run it from the observer directory:

```sh
python supervisor_service.py --config ../self-hosted-nodes.json --host 127.0.0.1 --port 8765 --interval 5 --max-snapshot-age 15
```

The configuration file must be a private deployment copy, not the example file. It must pin independently verified chain identities and list only SOBYA-operated private node URLs. The example config remains all-disabled and is intentionally rejected by the service.

Read-only endpoints:
- `GET /healthz`: confirms the process is responding and reports whether a health snapshot exists.
- `GET /ready?network=ethereum`: returns HTTP 200 only when the latest non-stale snapshot says every configured node for that network is healthy; otherwise returns HTTP 503.
- `GET /admission?source=tron&destination=sobya`: returns HTTP 200 only when both the source and destination networks are ready; otherwise returns HTTP 503. The destination defaults to `sobya` if omitted.
- The network value may be `ethereum`, `tron`, `solana`, or `sobya`, provided that network is explicitly enabled and configured.

The service refuses non-loopback bind addresses. Keep it behind a local order API or private host boundary; do not expose it directly to the public internet. A consumer must treat every non-200 response, timeout, malformed response, or unknown network as **not ready**. This service is a health/readiness gate only: it does not itself accept orders, integrate with the coordinator, stop an existing order API, sign, or broadcast transactions. The coordinator/order API must check `/admission` before issuing a quote and again before accepting a source deposit. There is not yet an HTTP order/quote API in this repository, so no live order endpoint has been connected to this gate. The admission endpoint and live-node tests remain outstanding.

The monitor clears its snapshot if a refresh operation raises, and stale snapshots fail closed. It does not preserve a previously healthy result after a probe exception.

## Implementation gates

1. Implemented: independent config/order PDA derivation and forged-PDA rejection tests in the Solana source observer. Still pending: validator-based integration tests.
2. Added a self-hosted node configuration template with public-RPC fallback disabled; all networks remain disabled and example identities must be pinned before use.
3. Added a fail-closed supervisor library and read-only probe adapters for Ethereum/SOBYA EVM, TRON FullNode+SolidityNode, and Solana JSON-RPC. The adapters check EVM chain ID/head/finalized tag/syncing, TRON genesis/head/solidified height, and Solana genesis/health/processed+finalized slots. They use bounded HTTP responses/timeouts and reject public RPC URLs. Mocked unit tests cover adapter behavior; no live-node connection or testnet integration has been performed. Current adapters use each node's own head as the reference height, so cross-node peer-head comparison is not yet supplied by the adapters. They do not independently verify consensus or act as light clients. The config-to-supervisor factory is implemented, but deployment and wiring into a running supervisor service remain pending.
4. Implement separately isolated SOBYA-controlled attestor processes and key lifecycle; keep all signing disabled by default.
5. Add coordinator/risk-controller integration, strict caps, pause and refund-preservation tests.
6. Run end-to-end tests on each source-chain test network and SOBYA test environment.
7. Review the single-operator trust model and publish it honestly in the DEX UI.
8. Enable any network only after explicit owner approval. No mainnet deployment, signing, escrow claim, or funds movement is authorized by this document.

## Coordinator admission boundary (library stage)

The coordinator now includes `cross-chain/coordinator/admission.py`.
`ReadinessAdmissionGuard` checks both the selected source network and SOBYA
through the in-process supervisor monitor before recording a quote, and checks
again before accepting verified source-deposit evidence. Any unhealthy,
unknown, stale, malformed, or unavailable readiness result denies that new
admission step. The guard deliberately does not gate destination-payout
recording for an already-funded order, so a pause for new orders does not
prevent an existing order from progressing toward safe completion.

This is currently an **in-process library integration**, not a running order
API. No network listener, public quote endpoint, authentication, inventory
reservation, or API-to-ledger wiring exists yet. A future local coordinator
API must exclusively use this guard for quote and deposit admission; direct
ledger access would bypass the protection. Refunds remain governed by the
source escrow's on-chain deadline path and must never be disabled by this
readiness gate. The readiness check and ledger write are not an atomic
cross-system transaction, so the API must recheck at each admission boundary
and fail closed.

CI now runs the guard tests alongside the ledger tests. Passing these unit
tests does not establish live-node readiness or production operation.

## Local coordinator orchestration and solver inventory

The coordinator now has an in-process orchestration module
(`cross-chain/coordinator/coordinator.py`) that requires explicit verifier
callbacks for signed quotes and finalized source/destination evidence. It
rejects missing verifiers, false results, ambiguous results, and verifier
exceptions. New quotes pass through the dual-chain readiness guard and reserve
the exact SOBY payout amount in the SQLite ledger in the same database
transaction as quote registration. This prevents two quotes from promising
the same unreserved solver units.

Solver inventory is provisioned locally by a trusted operator in SOBY base
units (18 decimals). A verified destination payout consumes the reservation
and reduces the solver's tracked total inventory. This accounting is an
operational reservation record; it does not prove an on-chain wallet balance.
Before production, inventory provisioning must be reconciled with finalized
SOBYA balances and protected from unauthorized local access.

The coordinator is **not yet an HTTP API** and has no caller authentication,
production signature verifiers, live observer bindings, signing keys, relayer,
or transaction broadcast. The injected verification callbacks are placeholders
for audited chain-specific verification implementations, not a claim that
verification has already been integrated. No order can be safely offered to
public users until those components and end-to-end tests exist.

## Authenticated local coordinator API

An HTTP adapter now exists at `cross-chain/coordinator/http_api.py`. It binds
only to loopback and requires a bearer token of at least 32 UTF-8 bytes. Its
three POST routes accept signed quotes, verified source-deposit proofs, and
verified destination-payout proofs. The request body is JSON, bounded to 64
KiB by default, and record fields are schema-checked. Quote requests are gated
by node readiness and atomic solver inventory reservation. Existing funded
orders can still progress through verified destination payout while new-order
admission is paused.

The server is a programmatic adapter, not an enabled production daemon. It
cannot start without the application supplying a bearer token and all three
chain-specific verifier callbacks. Those callbacks are security-critical and
are not yet implemented as production verifiers. Keep the API on loopback;
do not expose it publicly or put a token in the repository. It has no quote
pricing engine, automatic signature creation, RPC client, signer, relayer,
escrow claim/refund automation, or on-chain inventory oracle. No server was
started and no node or transaction was contacted.
