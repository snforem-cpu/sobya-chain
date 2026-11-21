# SOBYA Cross-Chain Swap Threat Model

Status: initial review checklist; not a security audit.

## Assets to protect

- User USDT deposited into source-chain order escrow.
- Solver SOBY inventory and any explicitly designated reserve.
- Order uniqueness, recipient binding, and quote integrity.
- DEX users' wallet approvals and transaction intent.
- Availability of safe refunds during relayer, solver, or RPC outages.

## Trust boundaries

1. User wallet and browser.
2. Quote/order API.
3. TRON, Ethereum, and Solana RPC providers.
4. SOBYA-operated observers/attestors or a light-client verifier.
5. Source-chain escrow contracts/program.
6. SOBYA settlement contract and solver wallet.
7. Monitoring, pause authority, and key-management infrastructure.

No API response, single RPC response, browser event, or project-operated database entry is sufficient proof of a cross-chain deposit. The Ethereum prototype observer uses the finalized block tag and verifies escrow storage plus the funding event, but production operation still requires multiple independent RPC operators and independent attestor review.

## Principal threats and required controls

| Threat | Required control |
|---|---|
| Fake deposit / forged RPC response | SOBYA-operated node checks plus observer cross-checks; bind exact source chain, escrow, token, sender, amount, order ID, and finalized transaction |
| Reorg or non-final transaction | Chain-specific finality policy; reject non-final evidence; re-check before payout |
| Replay/double spend | Unique order ID, consumed-deposit mapping, chain/domain separation, nonce, idempotent transitions |
| Wrong token or counterfeit USDT | Exact reviewed contract/mint allowlist; decimals and token-program validation |
| Quote manipulation | Signed quote, short expiry, fixed destination, explicit minimum output/fee and solver commitment |
| Solver fails to pay | Escrow refund deadline and on-chain mutually exclusive payout/refund state |
| Solver claims without payout | Source escrow claim requires valid destination payout proof |
| Compromised attestors | SOBYA-controlled threshold keys isolated by process/host, rate limits, strict caps, monitoring, pause and recovery plan; disclose single-operator compromise risk |
| Admin key compromise | No arbitrary escrow withdrawal; separated roles; timelock for sensitive configuration; hardware-backed keys |
| Solvency failure | Reserve accounting, inventory reservation, per-order caps, stop quoting when inventory is unavailable |
| RPC outage or censorship | Multiple SOBYA-operated node instances where feasible, monitoring, delayed settlement rather than unsafe acceptance; no public-RPC fallback |
| Malicious token behavior | Exact token allowlist, measured transfers, reject fee-on-transfer/rebasing assets unless explicitly supported |
| Frontend compromise | Reproducible static build, strict contract allowlists, wallet transaction preview, no private keys in browser |

## Mandatory test cases

- Valid deposit on each source chain.
- Wrong token contract/mint, wrong chain, wrong escrow, wrong recipient, wrong amount.
- Duplicate event and replayed proof.
- Source transaction dropped, reverted, or reorganized before finality.
- Expired quote and late deposit.
- Solver payout delayed, reverted, or sent to the wrong recipient.
- Refund and solver claim attempted concurrently.
- RPC disagreement and outage.
- Attestor threshold unavailable or compromised.
- Per-order and global limits reached.
- Pause/unpause while funds are escrowed.
- Solana finalized commitment and token-program/mint edge cases.
- TRON solidified block and event decoding edge cases.
- Ethereum finality/reorg and log-index uniqueness edge cases.

## Release gates

No testnet deployment until the state machine, contracts/programs, property tests, and threat review are complete. No mainnet deployment until independent security review, source token address verification, operational key separation, monitoring, funded solver inventory, incident/refund procedures, and explicit owner approval are complete.

The initial documentation milestone does not satisfy any deployment or audit gate.


## Security hardening applied in the implementation branch

The following fail-closed controls have been added after the initial threat review:

- The coordinator runtime now requires at least three uniquely named source-observer replicas and three destination-observer replicas. It derives a strict-majority quorum (or validates an explicitly configured threshold), requires distinct private RPC URLs per network, and invokes every configured verifier before accepting source-deposit or destination-payout evidence.
- The destination payout observer now requires the receipt block to be covered by the SOBYA EVM `finalized` checkpoint. A configurable confirmation depth remains an additional policy check; confirmations alone are no longer treated as finality.
- The self-hosted supervisor now requires at least two configured nodes for each enabled network and compares each observed head against the highest head observed from the configured local nodes. It no longer trusts a node's self-reported head as its own reference.
- Quote pricing now requires a finalized native-SOBY balance reader. The runtime requires that reader to use the same pinned SOBYA node and chain ID as payout verification. New quotes are limited to the lower of ledger-available inventory and finalized on-chain balance after subtracting existing reservations.
- Ethereum/TRON escrow and Solana escrow initialization now require at least three distinct attestors and a strict-majority threshold.

## Remaining trust and release limitations

These controls improve fault detection and inventory safety but do **not** establish independent-operator decentralization. Distinct RPC URLs can still point to nodes controlled by the same administrator, and the code cannot prove that attestor keys belong to different people or organizations. A colluding threshold of attestors can still authorize a false source-chain release. Key rotation/revocation, signer isolation, secure key provisioning, incident pause/recovery, and independent operator governance remain operational/security design work.

The TRON wrapper still requires TRON-specific compiler validation and Shasta/TVM execution tests. Solana still requires validator-based integration tests. The new runtime composition and finalized-balance path require CI verification and later testnet integration. No network has been enabled, no contract deployed, no signing service started, and no funds moved. These changes do not authorize mainnet operation.
