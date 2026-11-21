# Local cross-chain order model

This is a deterministic reference state machine used to test order lifecycle invariants before implementing chain-specific escrow programs.

## Run

From the repository root:

```sh
python3 -m unittest discover -s cross-chain/model -p 'test_*.py' -v
```

No third-party dependencies, wallet, RPC endpoint, private key, or network access is required.

## What it tests

- Order uniqueness and expiry.
- Solver binding.
- Exact source-chain/token/escrow/sender/amount/order binding.
- Independent finality flag and verifier identity presence.
- Source transaction replay prevention.
- Destination chain/recipient/amount/order binding.
- Payout finality before solver claim.
- Mutually exclusive refund and successful settlement terminal states.
- Refund deadlines.

## Critical limitation

The model accepts proof objects as inputs and checks their fields. It does **not** cryptographically verify a TRON receipt, Ethereum log, Solana transaction, validator signature, light-client proof, or SOBYA transaction. The booleans and verifier IDs are simulation inputs only. They must never be accepted directly from an untrusted browser or API in production. Real chain adapters must independently verify finalized source events and destination payouts, and on-chain escrow contracts/programs must enforce the same terminal-state rules.
