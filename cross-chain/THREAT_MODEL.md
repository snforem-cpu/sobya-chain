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
4. Independent observers/attestors or light-client verifier.
5. Source-chain escrow contracts/program.
6. SOBYA settlement contract and solver wallet.
7. Monitoring, pause authority, and key-management infrastructure.

No API response, single RPC response, browser event, or project-operated database entry is sufficient proof of a cross-chain deposit.

## Principal threats and required controls

| Threat | Required control |
|---|---|
| Fake deposit / forged RPC response | Independent verification; bind exact source chain, escrow, token, sender, amount, order ID, and finalized transaction |
| Reorg or non-final transaction | Chain-specific finality policy; reject non-final evidence; re-check before payout |
| Replay/double spend | Unique order ID, consumed-deposit mapping, chain/domain separation, nonce, idempotent transitions |
| Wrong token or counterfeit USDT | Exact reviewed contract/mint allowlist; decimals and token-program validation |
| Quote manipulation | Signed quote, short expiry, fixed destination, explicit minimum output/fee and solver commitment |
| Solver fails to pay | Escrow refund deadline and on-chain mutually exclusive payout/refund state |
| Solver claims without payout | Source escrow claim requires valid destination payout proof |
| Compromised attestors | Independent threshold, key rotation, rate limits, caps, monitoring, pause and recovery plan |
| Admin key compromise | No arbitrary escrow withdrawal; separated roles; timelock for sensitive configuration; hardware-backed keys |
| Solvency failure | Reserve accounting, inventory reservation, per-order caps, stop quoting when inventory is unavailable |
| RPC outage or censorship | Multiple independent RPC sources, monitoring, delayed settlement rather than unsafe acceptance |
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
