# Solana USDT escrow program (prototype)

This is a native Solana program using the legacy SPL Token program. It is not an
Anchor program. The program uses PDAs for the immutable config and each order.

## Order flow

1. Initialize an authority-scoped config PDA (derived from the initializer's
   public key) with the USDT mint, SOBYA EVM chain ID, an immutable attestor
   public-key set (maximum 16), and a threshold. Each authority has a separate
   config; the DEX must pin the intended config address and never trust an
   arbitrary user-supplied config.
2. Create the escrow token account as the associated token account for the
   order PDA and the configured USDT mint. This account must be owned by the
   legacy SPL Token program; Token-2022 is not supported by this prototype.
3. The user funds an order. The solver must co-sign the funding transaction;
   this on-transaction signature is the solver's commitment to the exact order
   fields (source amount, destination recipient/amount, quote expiry/refund
   deadline). The program transfers the exact SPL-token amount into escrow.
4. Independent attestors submit separate signed `AttestPayout` instructions.
   Each configured attestor can attest once, and every attestation must bind
   the same SOBYA destination transaction hash.
5. After the threshold is reached, only the committed solver can claim the
   escrowed USDT. The user can refund after the deadline while the order remains
   funded. Claim and refund are mutually exclusive because both update the same
   order PDA.
   
## Security boundaries

- This is a prototype, not an audited or deployed program.
- Attestors are a fixed trust set. Their on-chain signatures prove which
  configured keys approved the payout hash; they do not prove SOBYA finality
  cryptographically. Attestors must independently verify SOBYA.
- Solver commitment is provided by co-signing the funding transaction rather
  than a detached EIP-712 quote. The wallet flow must collect both signatures.
- Each config is bound to its initializer's public key and has no update or withdrawal instruction. The program has no admin
  escrow withdrawal path.
- The program supports one configured legacy SPL USDT mint per deployment.
  The exact mainnet mint must be independently verified before configuration.
- The escrow ATA must be created for the order PDA before funding. Token-2022,
  transfer-hook mints, fee-on-transfer semantics, and arbitrary token programs
  are unsupported.
- The program ID is supplied by the deployment and used for PDA derivation;
  a deployment keypair and upgrade-authority policy must be selected before
  testnet use. A deployer retaining upgrade authority can still replace program
  code, so immutable/renounced upgrade authority is a separate operational step.
- No Solana testnet or mainnet deployment has occurred.

## Build and test

From this directory:

```sh
cargo fmt --check
cargo test
cargo check
```

These checks compile and test the Rust program locally. They do not execute it
inside a Solana validator. Before testnet deployment, add validator-based
integration tests covering PDA/ATA derivation, SPL Token CPI, account ownership,
attestor replay, wrong-mint rejection, and refund-versus-claim races.
