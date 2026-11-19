# SOBYA DEX (development)

This directory contains the first self-custody web interface for the planned SOBYA exchange.

## Network
- Network: SOBYA Mainnet
- EVM chain ID: 357812033857
- Native asset: SOBY (18 decimals)
- RPC: https://sobya-evm-rpc.nodesafe-dapp.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya

## Current status
The UI is intentionally deployment-gated. `config.json` has empty Factory, Router and WSOBY addresses. The interface will not enable transactions until all three valid contract addresses are supplied. Do not fill these fields with mock, testnet, third-party, or guessed addresses.

The existing `contracts/src/WSOBY.sol` is source code only; its presence in GitHub does not prove it is deployed. The DEX contracts (Factory, Pair, Router), their integration tests, bytecode verification and mainnet deployment are still required before trading can be enabled.

## Safety
- Never commit a wallet private key or seed phrase.
- Never use an unverified token address. Token symbols are not proof of identity.
- Pool creation and swaps require user-signed transactions and network gas.
- Minimum received is explicitly supplied by the user; the UI does not silently choose a slippage tolerance.
- The current liquidity action uses a conservative 2% minimum-amount bound, but production release must add a reviewed quote/reserve calculation and remove this provisional path if it is not acceptable.
- No USDT contract is configured. Do not label a token as USDT unless its issuer and contract are independently verified.

## Local preview
Serve this directory over HTTP (for example, with Python's built-in static server) and open it in a browser with an EVM wallet installed. GitHub Pages serves the same static files once the branch is merged and Pages deploys.

## Required before production
1. Add a reviewed, license-compliant AMM core and router with pinned source/compiler settings.
2. Add Foundry unit, fuzz and end-to-end tests for pool creation, LP mint/burn, swaps, fee accounting, deadlines, slippage and WSOBY native wrapping.
3. Run CI and verify exact pair init-code hash compatibility.
4. Deploy Factory, Router and WSOBY using a wallet controlled by the project owner; record transaction hashes and addresses.
5. Verify contract source/bytecode on the explorer and publish the addresses in `config.json`.
6. Audit the contracts and have an independent reviewer examine the deployment configuration before enabling public trading.

No protocol upgrade, genesis change, or paid backend is needed for this architecture.
