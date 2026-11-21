# SOBYA DEX mainnet deployment guide

## Deployment model
The deployment is owner-signed and is never run by GitHub Actions. It creates four contracts: WSOBY, Factory, TWAP Oracle, and Router. The independent security review is complete and the current SOBYA EVM endpoint passed the read-only RPC preflight and disposable mainnet-fork deployment simulation. The compile-time approval gate is enabled for owner-controlled deployment. Every broadcast still requires explicit local wallet authorization. Do not treat this as an RPC or wallet failure.

This guide prepares the owner-controlled process; it does not mean the contracts have been audited, approved, or deployed. The gate must only be changed in a separately reviewed release after the owner has reviewed the residual risks and independent security review findings. No private key is needed for the preflight.

## Requirements
- Foundry installed locally (`cast` and `forge`).
- SOBYA EVM RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`.
- Expected EVM chain ID: `357812033857`.
- Owner-controlled wallet with enough native SOBY for four contract creations and a safety margin.
- A local encrypted Foundry keystore. Never paste a private key or seed phrase into ChatGPT, GitHub, a website, or a repository file.

## 1. Read-only RPC preflight
From the repository root:

```sh
sh contracts/script/check-sobya-mainnet.sh
```

The script checks the EVM RPC chain ID, latest block number, and gas-price response. It is read-only: it does not access a wallet or send transactions. Stop if it fails. A successful preflight proves basic RPC reachability only; it does not prove contract compatibility or safety.

## 2. Prepare a local Foundry keystore
From the repository's `contracts` directory, import the owner's wallet into Foundry's encrypted local keystore:

```sh
cast wallet import sobya-owner --interactive
cast wallet address --account sobya-owner
```

Enter the private key only into Foundry's local interactive prompt. Choose a strong keystore password. Do not put the key in a shell command, environment variable, `.env` file, GitHub, a website, or this chat. Keep the keystore and password on your own device. Verify the displayed address carefully.

## 3. Confirm network and funding
```sh
export SOBYA_RPC="https://sobya-evm-rpc.nodesafe-dapp.xyz"
cast chain-id --rpc-url "$SOBYA_RPC"
cast block-number --rpc-url "$SOBYA_RPC"
cast balance <OWNER_ADDRESS> --rpc-url "$SOBYA_RPC"
```

The EVM chain ID must be exactly `357812033857`. Confirm the owner address and ensure sufficient native SOBY for four contract deployments plus a margin. Do not proceed on a different chain or with uncertain gas funding.

## 4. Approval gate and simulation
The current source contains:

```solidity
bool private constant DEPLOYMENT_APPROVED = true;
```

The independent audit and exact-chain integration checks have been completed. Simulate first, review the output and wallet, and broadcast only when the owner is ready. The gate does not automate or authorize transactions on the owner's behalf.

After an authorized release has changed the gate, simulate without broadcasting:

```sh
forge script script/DeploySobyaDex.s.sol:DeploySobyaDex --rpc-url "$SOBYA_RPC" --account sobya-owner
```

Review the full output, deployer address, four predicted creations, constructor arguments, and estimated gas. Stop on any warning, mismatch, or unexpected address.

## 5. Owner-signed deployment
Only after the simulation has been reviewed and the owner explicitly decides to proceed:

```sh
forge script script/DeploySobyaDex.s.sol:DeploySobyaDex --rpc-url "$SOBYA_RPC" --account sobya-owner --broadcast
```

Foundry will request the local keystore password when needed. The owner must verify the MetaMask/keystore account, SOBYA Mainnet network, and gas estimate before authorizing. Keep transaction hashes and receipts.

## 6. Verify all four deployments
For each deployment transaction, confirm on the SOBYA explorer:
- Successful receipt and expected sender.
- Contract-creation receipt and non-empty deployed contract address.
- WSOBY name `Wrapped SOBYA`, symbol `WSOBY`, 18 decimals, and no premint.
- Oracle `factory()` equals the deployed Factory.
- Router `factory()` and `wrappedSoby()` equal the deployed Factory and WSOBY.
- Factory starts with no pairs unless an intentional pair creation has already occurred.

Do not publish addresses copied from simulation output. Use only addresses from confirmed mainnet receipts. If any constructor relationship or receipt is wrong, stop and do not open the DEX frontend.

## 7. Publish configuration and verify user flows
Only after all four addresses are independently read back from the live chain should a reviewed change populate `dex/config.json` fields `wrappedSoby`, `factory`, `oracle`, and `router`, and set `deploymentStatus` to `ready`. Then publish the static frontend.

Owner-led smoke test, beginning with tiny amounts:
1. Connect MetaMask to SOBYA Mainnet and verify the chain ID.
2. Confirm WSOBY deposit/withdrawal round-trip and balances.
3. Create a test pair and verify Factory registration.
4. Add a tiny amount of liquidity; verify reserves and LP-token balances.
5. Execute a tiny swap in each direction; verify receipts, output amounts, and fee accounting.
6. Remove a small portion of liquidity and verify returned tokens.
7. Wait at least 30 minutes before testing the Oracle's first valid TWAP observation; verify stale/too-short observations are rejected.
8. Record transaction hashes and compare every balance/reserve change with expected values. Stop on any mismatch; do not invite public liquidity until the owner has reviewed results.

## Critical limitations
- No independent smart-contract audit is represented by this guide.
- The TWAP Oracle is a pool-specific time-weighted reference with a 30-minute minimum and 2-hour maximum observation window. It is NOT a global price oracle, USD feed, proof of market-wide value, or safe collateral price by itself.
- The AMM supports ordinary ERC-20 token pairs; it does not create or guarantee genuine USDT.
- A successful read-only RPC preflight or local Foundry test is not proof of live contract correctness.
- Never disclose a seed phrase/private key or upload it to GitHub Actions. The owner signs deployment locally.


---

# Cross-chain inventory vault deployment (separate from the DEX)

The cross-chain settlement pair is separate from the existing DEX deployment
guide above. `script/DeploySobyaInventory.s.sol` deploys:

1. `SobyaSolverInventoryVault`
2. `SobyaCrossChainSettlement` with three distinct attestor addresses and a
   2-of-3 strict-majority threshold
3. The vault's one-time settlement link

The script refuses to run unless `block.chainid == 357812033857`. It reads
the deployer key and attestor addresses from the local process environment.
It does not generate, store, or transmit private keys.

## Build and simulation

From `contracts/`:

```sh
forge build
forge test -vvv
```

Set these values in a private shell or local secret manager, never in a
committed file:

- `SOBYA_DEPLOYER_PRIVATE_KEY`: local deployer key for SOBYA EVM
- `SOBYA_ATTESTOR_1`, `SOBYA_ATTESTOR_2`, `SOBYA_ATTESTOR_3`: three distinct
  SOBYA-controlled EVM addresses whose keys are separately stored and
  controlled by the SOBYA operator

Use only the verified, private SOBYA EVM RPC endpoint. Simulate first and
confirm the exact chain ID, deployer, attestor addresses, deployment
addresses, constructor state, and estimated gas. The script is a deployment
preparation artifact; it has not been run and no cross-chain vault has been
deployed by this change.

## After deployment

Independently verify the runtime bytecode, owner, attestor membership,
2-of-3 threshold, and reciprocal vault/settlement link. Then each solver must
deposit native SOBY into the vault. The ordinary wallet balance is not
spendable cross-chain inventory. The coordinator now reconciles quotes against
the vault's finalized `available(solver)` view and the local ledger.

Do not enable a source chain until its escrow/program is deployed and verified
on that chain's testnet, the correct USDT token/mint is pinned, SOBYA-operated
nodes are synchronized, and end-to-end attestation signing and claim/refund
tests have passed. The TRON wrapper requires a TRON-distributed Solidity
compiler and Shasta TVM verification; Foundry EVM tests do not prove TVM
compatibility. The Solana program still requires validator-based integration
tests and a verified deployment/program ID.

## Security boundary

- The three attestor keys are separate signing identities administered by one
  SOBYA operator. This is not independent third-party decentralization.
- This script only deploys and links the SOBYA vault and settlement contracts.
  It does not fund the vault, deploy source escrows, start observers, run the
  coordinator, sign attestations, claim USDT, or enable the DEX.
- Keep all source networks disabled until live testnet integration and
  independent security review are complete.
