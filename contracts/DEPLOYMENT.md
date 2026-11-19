# SOBYA DEX mainnet deployment guide

## Deployment model
The deployment is owner-signed and is never run by GitHub Actions. It creates four contracts: WSOBY, Factory, TWAP Oracle, and Router. The deployment script currently has a deliberate compile-time approval gate set to `false`. **With that gate closed, both simulation and broadcast are expected to revert with `SOBYA DEX: AUDIT_GATE_LOCKED`.** Do not treat this as an RPC or wallet failure.

This guide prepares the owner-controlled process; it does not mean the contracts have been audited, approved, or deployed. The gate must only be changed in a separately reviewed release after the owner has reviewed the residual risks and independent security review findings. No private key is needed for the preflight.

## Requirements
- Foundry installed locally (`cast` and `forge`).
- SOBYA EVM RPC: `https://sobya-rpc.nodesafe-dapp.xyz`.
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
export SOBYA_RPC="https://sobya-rpc.nodesafe-dapp.xyz"
cast chain-id --rpc-url "$SOBYA_RPC"
cast block-number --rpc-url "$SOBYA_RPC"
cast balance <OWNER_ADDRESS> --rpc-url "$SOBYA_RPC"
```

The EVM chain ID must be exactly `357812033857`. Confirm the owner address and ensure sufficient native SOBY for four contract deployments plus a margin. Do not proceed on a different chain or with uncertain gas funding.

## 4. Approval gate and simulation
The current source deliberately contains:

```solidity
bool private constant DEPLOYMENT_APPROVED = false;
```

Therefore the deployment script cannot currently simulate or broadcast successfully. A separately reviewed release must explicitly authorize the deployment by changing this gate, after reviewing the independent audit status and the exact-chain integration evidence. Do not work around the gate or edit it casually.

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
