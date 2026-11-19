# SOBYA DEX deployment guide

## Deployment is owner-signed
This deployment is deliberately not run by GitHub Actions. It uses a local wallet key through Foundry and sends four transactions: WSOBY, Factory, TWAP Oracle, and Router. Never paste a private key or seed phrase into ChatGPT, GitHub, a website, or a repository file.

## Requirements
- Foundry installed locally.
- A wallet controlled by the SOBYA project owner.
- Native SOBY in that wallet for deployment gas.
- SOBYA EVM RPC: `https://sobya-evm-rpc.nodesafe-app.xyz`.
- Expected EVM chain ID: `357812033857`.

## 1. Prepare a local Foundry keystore
From the repository's `contracts` directory, import the owner's wallet into Foundry's encrypted local keystore:

```sh
cast wallet import sobya-owner --interactive
cast wallet address --account sobya-owner
```

Enter the private key only into Foundry's local interactive prompt. Choose a strong keystore password. Do not put the key in a shell command, environment variable, `.env` file, GitHub, a website, or this chat. Keep the keystore and password on your own device.

## 2. Confirm the network before broadcasting
```sh
export SOBYA_RPC="https://sobya-evm-rpc.nodesafe-app.xyz"
cast chain-id --rpc-url "$SOBYA_RPC"
```
The result must be exactly `357812033857`. Stop if it differs. Check that `cast wallet address --account sobya-owner` is the intended owner wallet and that it has enough native SOBY for four contract deployments.

## 3. Simulate first
```sh
forge script script/DeploySobyaDex.s.sol:DeploySobyaDex --rpc-url "$SOBYA_RPC" --account sobya-owner
```
Review the simulation output, deployer address, predicted contract creations and estimated gas. The script itself also hard-reverts unless `block.chainid == 357812033857`.

## 4. Deploy after checking the simulation
```sh
forge script script/DeploySobyaDex.s.sol:DeploySobyaDex --rpc-url "$SOBYA_RPC" --account sobya-owner --broadcast
```
Foundry will request the local keystore password when needed. Confirm each wallet transaction only after checking the destination network and estimated gas. Keep transaction records private until you have confirmed each transaction on the SOBYA explorer.

## 5. Verify the deployments
For each of the four addresses printed by the script:
- Open the corresponding transaction in the SOBYA explorer.
- Confirm successful status, sender address, contract-creation receipt and deployed contract address.
- Confirm WSOBY has name `Wrapped SOBYA`, symbol `WSOBY`, 18 decimals and no premint.
- Confirm Factory reports no pairs initially.
- Confirm Oracle's `factory()` matches the Factory, and Router's `factory()` and `wrappedSoby()` match the Factory and WSOBY addresses.

Only after all four are verified should their exact addresses be entered in `dex/config.json` as `wrappedSoby`, `factory`, `oracle`, and `router`; set `deploymentStatus` to `ready` only in the same reviewed change. Then publish the static frontend.

## Important
This is a new WSOBY deployment and will have its own address; do not reuse a guessed or old address. This guide does not claim the contracts are audited. An independent security review and live-runtime integration check are still recommended before inviting public liquidity. The AMM supports ordinary ERC-20 token pairs only; it does not provide an official USDT token. The TWAP Oracle is a pool-specific time-weighted reference with a 30-minute minimum and 2-hour maximum observation window. It is NOT a global price oracle, USD feed, proof of market-wide value, or safe collateral price by itself. Consumers must enforce liquidity/depth requirements and compare independent external markets. The oracle has no admin or emergency pause; a bad pair market or compromised factory remains a source risk.
