# SOBYA destination settlement and inventory custody

`SobyaSolverInventoryVault` and `SobyaCrossChainSettlement` are deployed as a
pair on the SOBYA EVM network. The vault holds native SOBY deposited by a
solver, tracks the solver's available and reserved balances, and locks a fixed
amount to one order and recipient. The settlement contract can execute only
that exact reservation after a strict-majority source-deposit attestation.

## Order flow

1. The solver deposits native SOBY into `SobyaSolverInventoryVault`.
2. The local coordinator verifies the signed quote, finalized solver balance,
   and dual-chain readiness.
3. The concrete `SobyaVaultReserver` submits
   `reserve(orderId, recipient, amount, releaseAfter)` using a signer supplied
   by the local operator. It checks the SOBYA chain ID, deployed vault code,
   transaction fields, successful receipt, canonical block, finalized
   checkpoint, exact `InventoryReserved` event, and reservation readback.
4. The vault's one-time owner configuration binds the deployed settlement contract. The vault rejects direct payout calls from every other address; only that settlement contract can execute a reservation.
5. The source-chain user funds the matching USDT escrow on Ethereum, TRON, or
   Solana.
6. The source attestors independently verify the finalized source deposit and
   sign the EIP-712 or Solana attestation for the exact order.
7. The settlement contract verifies the strict-majority signatures, reads the
   fixed vault reservation, and calls `executePayout(orderId)`. The vault
   sends native SOBY only to the reserved recipient.
8. Source-chain attestors may then authorize the solver's source escrow claim
   after independently verifying the finalized `PayoutExecuted` event.
9. An unused reservation can be released only after its deadline. The
   source-chain escrow refund path remains governed by its own deadline.

The source escrow and destination settlement do not provide atomic
cross-chain execution. The attestor threshold is a trust boundary, not a
trustless light client. In the self-hosted model, SOBYA controls the nodes and
attestor infrastructure; multiple processes do not imply independent
operators.

## Deployment preparation

An owner-run Foundry script is provided at
`contracts/script/DeploySobyaCrossChain.s.sol`. It deploys the vault first and
then deploys settlement with that exact vault address. It requires:

- `SOBYA_EXPECTED_CHAIN_ID`: explicitly pinned chain ID for the target network.
- `SOBYA_CROSS_CHAIN_DEPLOYMENT_APPROVED=true`: local explicit deployment
  approval; absent or false values block deployment.
- `SOBYA_ATTESTOR_1`, `SOBYA_ATTESTOR_2`, and `SOBYA_ATTESTOR_3`: three
  distinct nonzero public addresses. The deployed threshold is 2 of 3.
- A local Foundry keystore selected with `--account`; no private key belongs in
  environment variables, repository files, CI, or this chat.

Example after successful compilation, testnet validation, and review:

```sh
cd contracts
export SOBYA_EXPECTED_CHAIN_ID=<verified-target-chain-id>
export SOBYA_CROSS_CHAIN_DEPLOYMENT_APPROVED=true
export SOBYA_ATTESTOR_1=<attestor-public-address-1>
export SOBYA_ATTESTOR_2=<attestor-public-address-2>
export SOBYA_ATTESTOR_3=<attestor-public-address-3>
forge script script/DeploySobyaCrossChain.s.sol:DeploySobyaCrossChain \
  --rpc-url "$SOBYA_RPC" --account sobya-owner --broadcast
```

The environment approval is a deployment gate, not evidence that the deployment
is safe. Review the target chain ID, RPC endpoint, attestor addresses, wallet,
gas estimate, and deployment receipt before broadcasting. Record and verify
both emitted contract addresses from the actual receipt; never copy or invent
addresses from source code.

## Current status and release blockers

- Solidity vault and settlement source plus Foundry tests are present.
- The Python vault adapter is implemented and has mock-based tests; runtime
  composition requires that concrete adapter and the same pinned SOBYA RPC
  used by the payout observer.
- The deployment script is preparation only. Neither contract is confirmed
  deployed by this repository, and no live deployment receipt/address is
  recorded here.
- No production local signer/attestor daemon or secure key lifecycle is
  provisioned. The adapter accepts a local signer callback; the operator must
  supply a secure signer implementation outside the repository.
- No live testnet end-to-end swap, source-escrow claim automation, or refund
  automation has been demonstrated.
- No DEX frontend/order API production deployment is wired to this flow.
- No independent security audit of the complete cross-chain system is claimed.

Do not enable deposits, quotes, or public trading until all source-chain
contracts/programs are deployed and verified on test networks, the local nodes
and attestors are running, full end-to-end deposit-to-payout-to-claim tests
pass, and the security review signs off. No mainnet deployment or funds
movement is performed by CI.
