# Solana source escrow observer (prototype)

Read-only verifier for deposits to the native Solana escrow program.

## Verification path

- Requests `getTransaction` with `commitment: finalized` and rejects missing or failed transactions.
- Requires the expected transaction signature and both the user and solver as signers, matching the on-chain `Fund` instruction's signer requirements.
- Locates exactly one instruction for the configured escrow program and order PDA, decodes its Borsh instruction payload, and matches the order ID, SOBYA recipient, destination amount, source amount, quote expiry, and refund deadline.
- Reads the order PDA at `finalized`, checks that it is owned by the configured program, decodes the exact 256-byte Borsh account layout, and matches all stored order fields and the `Funded` state.
- Reads the escrow token account at `finalized`, requires ownership by the legacy SPL Token program, and checks the USDT mint, order-PDA authority, and escrowed amount.

## Limitations

- The caller must pin the approved program ID and intended config PDA. The observer independently derives the config PDA from the user authority and the order PDA from the order ID, and rejects mismatches.
- The implementation supports the legacy SPL Token account layout, not Token-2022.
- This is a read-only library with mocked-RPC tests, not a signer, relayer, RPC quorum, or durable order service. A single RPC endpoint can lie.
- Validator-based integration tests and program deployment remain required before testnet or production use. The self-hosted operating profile is documented separately; multiple local nodes do not create independent-operator trust.
- No Solana program ID, USDT mint, or production RPC is configured.
