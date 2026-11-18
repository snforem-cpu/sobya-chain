# SOBYA DEX deployment guide

## Deployment is owner-signed
This deployment is deliberately not run by GitHub Actions. It uses a local wallet key through Foundry and sends three transactions: WSOBY, Factory, and Router. Never paste a private key or seed phrase into ChatGPT, GitHub, a website, or a repository file.

## Requirements
- Foundry installed locally.
- A wallet controlled by the SOBYA project owner.
- Native SOBY in that wallet for deployment gas.
- SOBYA EVM RPC: `https://sobya-evm-rpc.nodesafe-app.xyz`.
- Expected EVM chain ID: `357812033857`.

## 1. Prepare a local environment
From the repository's `contracts` directory, set the variables in your terminal session only:

```sh
export SOBYA_RPC="https://sobya-evm-rpc.nodesafe-app.xyz"
export PRIVATE_KEY="YOUR_PRIVATE_KEY_IN_YOUR_LOCAL_TERMINAL_ONLY"
```

Do not save the key in `.env` inside the repository and do not upload terminal screenshots showing it.

## 2. Confirm the network before broadcasting
```sh
cast chain-id --rpc-url "$SOBYA_RPC"
```
The result must be exactly `357812033857`. Stop if it differs.

## 3. Simulate first
```sh
forge script script/DeploySobyaDex.s.sol:DeploySobyaDex --rpc-url "$SOBYA_RPC"
```
Review the simulation output and estimated gas. Do not broadcast if any network or address is unexpected.

## 4. Deploy after checking the simulation
```sh
forge script script/DeploySobyaDex.s.sol:DeploySobyaDex --rpc-url "$SOBYA_RPC" --broadcast
```
Keep the terminal output and the broadcast transaction records private until you have confirmed each transaction on the SOBYA explorer.

## 5. Verify the deployments
For each address printed by the script:
- Open the corresponding transaction in the SOBYA explorer.
- Confirm successful status, sender address, contract-creation receipt and deployed contract address.
- Confirm WSOBY has name `Wrapped SOBYA`, symbol `WSOBY`, 18 decimals and no premint.
- Confirm Factory reports no pairs initially.
- Confirm Router's `factory()` and `wrappedSoby()` match the two addresses from this deployment.

Only after all three are verified should their exact addresses be entered in `dex/config.json` as `wrappedSoby`, `factory`, and `router`; set `deploymentStatus` to `ready` only in the same reviewed change. Then publish the static frontend.

## Important
This is a new WSOBY deployment and will have its own address; do not reuse a guessed or old address. This guide does not claim the contracts are audited. An independent security review and live-runtime integration check are still recommended before inviting public liquidity. The contracts currently support ordinary ERC-20 token pairs only; they do not provide an official USDT token.
