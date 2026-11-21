# Attestation payload protocol (no signer)

This module builds the exact payload shapes expected by the current source
escrow contracts. It deliberately contains no private-key loading, signature
creation, network transaction submission, or automated claim logic.

## Ethereum and TRON EVM/TVM escrow

`build_eip712_payout` constructs the EIP-712 typed data and
`eip712_payout_digest` computes the digest for:

- Domain name: `SOBYA Cross-Chain Escrow`
- Domain version: `1`
- Domain chain ID: the source chain's actual `block.chainid`
- Verifying contract: the exact source escrow address
- Payout struct: order ID, destination transaction hash, destination chain ID,
  destination recipient, destination SOBY amount, source escrow, source chain ID

The field order and types mirror `SobyaEthereumUsdtEscrow.claim`. A production
attestor must independently verify both source deposit and finalized SOBYA
payout evidence before signing. Signatures passed to the current Solidity
contract must be unique and sorted by recovered signer address ascending.

The caller must supply the real chain ID and escrow address from verified
deployment metadata. Do not assume the TRON TVM chain ID or reuse an Ethereum
signature across chains.

## Solana

`build_solana_attest_payout_instruction` returns the Borsh instruction bytes
for the existing `AttestPayout` enum variant (variant index 2), order ID, and
SOBYA destination transaction hash. Each attestor still needs to submit its
own signed Solana transaction; this module does not create or sign one.

## Security boundary

- This is deterministic serialization only, not a signer or signing service.
- Never place private keys, seed phrases, HSM credentials, or API secrets in
  this repository.
- Attestor keys must be independently controlled and isolated; threshold
  signing must not collapse into one shared hot key.
- Key rotation/revocation is not implemented in the immutable on-chain
  attestor sets. A compromise or lost key requires a separately reviewed
  redeployment/migration plan.
- External security review and chain-specific integration tests remain
  mandatory before any live signing or escrow claim.

## Local attestor signing service

`attestor_service.py` is the evidence-gated signing boundary:

- `sign_source_deposit` first invokes the configured source observer/quorum, then reads the exact active order reservation from finalized SOBYA vault state. It signs only when solver, recipient, SOBY amount, and release deadline match the immutable registered quote. Its EIP-712 domain is the SOBYA chain ID and exact settlement contract.
- `sign_evm_source_payout` first invokes the configured SOBYA destination observer/quorum and signs the source escrow's EIP-712 `Payout` only when the finalized receipt matches the immutable quote and pinned source escrow identity.
- `build_solana_payout_instruction` returns the Borsh `AttestPayout` instruction bytes after payout verification. Solana requires an attestor-signed transaction; this helper deliberately does not pretend instruction bytes are a signature or submit a transaction.
- The service accepts no caller-supplied digest or typed payload. Every signing path requires literal `True` from its independent verifier. EVM signatures are recovered locally and must match the configured attestor address.

### Encrypted EVM attestor key

`attestor_keystore.py` creates an owner-only encrypted key file using scrypt (N=32768, r=8, p=1) and PyNaCl SecretBox authenticated encryption. It refuses to overwrite an existing file, rejects symlinks and permissive file modes on load, and validates the decrypted key against the stored public address. `evm_signer_from_keystore(path, passphrase)` returns a local EVM signer.

Create each attestor keystore on that attestor's own machine using a fresh, unique key and a strong passphrase. Keep encrypted backups offline. Never commit keystore files, private keys, passphrases, or seed phrases. Do not copy the same private key to multiple attestors: a 2-of-3 policy is meaningful only when the keys are separately controlled. A Python process cannot guarantee memory zeroization; for higher assurance, replace the in-memory signer with a hardware wallet/HSM callback.

This is a signing library, not yet a supervised production daemon. It has no HTTP signing endpoint, no automatic Solana transaction construction/submission, no signer-to-signer coordination, and no key rotation. Do not enable it for mainnet until all three attestor instances are independently operated, observer quorums are connected to independently administered nodes, and end-to-end testnet and security review are complete.
