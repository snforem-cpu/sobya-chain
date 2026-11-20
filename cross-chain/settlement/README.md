# SOBYA destination settlement contract

`SobyaCrossChainSettlement` is the SOBYA-side native-SOBY payout endpoint for
the intent-based cross-chain flow.

A solver submits the source order identifiers and the exact source USDT amount,
and sends native SOBY as `msg.value`. The contract forwards that SOBY to the
user's SOBYA EVM address in the same transaction, marks the order paid, and
emits `PayoutExecuted`. The event binds the order ID, source-chain key, source
escrow identifier, source USDT contract/mint identifier, source amount,
destination recipient, SOBY amount, solver, and SOBYA chain ID.

Independent source-chain attestors must inspect the successful SOBYA
transaction/event and only then authorize the solver's source-escrow claim.
The settlement contract itself does not release source USDT and does not
cryptographically prove anything about TRON, Ethereum, or Solana.

## Safety properties

- One successful payout per order ID; duplicate order IDs revert.
- Native SOBY is forwarded atomically; failed recipient transfers revert the
  order state and the entire transaction.
- No owner, admin withdrawal, token mint, arbitrary release, or rescue method.
- The contract never accepts or represents source USDT; source escrow balances
  remain on their original chains.
- This is a prototype. It has not been deployed to SOBYA, audited, or integrated
  with a production solver/attestor service or DEX UI.

## Identifier encoding

Use canonical 32-byte chain keys (for example, hashes of documented network
identifiers). EVM/TVM 20-byte source escrow and token addresses must be
left-padded to 32 bytes. Solana program IDs and mint addresses are already
32-byte values. The source amount is expressed in the source token's smallest
units; the SOBY payout uses native SOBY's 18-decimal base units.

The source escrow and this destination contract do not provide atomic
cross-chain execution. The fixed threshold attestor model remains a trust and
liveness assumption.
