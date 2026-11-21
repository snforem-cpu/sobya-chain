# Ethereum USDT source escrow (testnet-first)

This is an isolated EVM source-chain escrow prototype. It is not deployed and is not yet audited.

## Flow

1. A solver signs an EIP-712 quote binding the order ID, user, exact USDT token, source amount, solver, SOBYA chain ID, SOBYA recipient, SOBY amount, quote expiry, and refund deadline.
2. The user approves the exact token amount and calls `fund`. The escrow checks the actual balance delta, rejecting fee-on-transfer behavior.
3. After the SOBY payout is final on SOBYA, the configured independent attestor threshold signs a domain-separated payout attestation. Only the committed solver can claim the source USDT.
4. If payout is not confirmed by the refund deadline, only the original user can refund. Claim and refund are mutually exclusive terminal states.

## Trust and limitations

- The verifier is a fixed threshold-attestor set. It is a trusted attestation model, NOT a light client and NOT trustless.
- The constructor is immutable: no owner, signer rotation, arbitrary withdrawal, or rescue function. Lost/compromised attestor keys therefore require a new escrow deployment and operational migration plan.
- This prototype handles Ethereum ERC-20 only. It does not implement TRON TVM or Solana.
- No production USDT address is hardcoded. The token address must be verified for the exact testnet before deployment.
- No testnet or mainnet deployment is authorized by this code change.
- Before any deployment: compile with Solidity 0.8.24, run Foundry tests, add invariant/fuzz tests, review EIP-712 signing compatibility, test adversarial ERC-20s and reentrancy, and obtain an independent security review.

## Build and test

From `contracts/` run:

```sh
forge test -vvv
```
