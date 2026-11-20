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
