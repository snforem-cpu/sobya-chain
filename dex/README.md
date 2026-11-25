# SOBYA DEX

Public self-custody DEX interface for SOBYA Mainnet.

## Mainnet connection

- Network: SOBYA Mainnet
- EVM chain ID: `357812033857`
- Native asset: SOBY (`asobya`, 18 decimals)
- EVM JSON-RPC: https://sobya-evm-rpc.nodesafe-dapp.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya

## Published contracts

The deployment configuration records these contract addresses as verified:

- Factory: `0x35f59c1Bb30e1FA29020294cB02Bd770D6e3fa8e`
- Router: `0x9F3B4AeFbCb937227Dac641Bf7b9e8b42d6CA23D`
- WSOBY: `0x9669a3d516B3423d90F1Ce81eAcF0B363369E09c`
- Oracle: `0xb76Aa2fe9459aEF38EB31D687c13D80bCf4716A4`

The public UI uses the current NodeSafe `nodesafe-dapp.xyz` EVM endpoint. Contract addresses in configuration are not, by themselves, proof of an active funded market.

## Current operating state

- Wallet connection and read-only contract queries use SOBYA Mainnet.
- Native SOBY / WSOBY wrapping is available when the connected wallet has sufficient SOBY for the amount and network fees.
- Pool creation and liquidity operations are enabled for owner-directed initialization.
- Public swaps are **disabled** until a funded pool, live reserves, quote accuracy, and controlled mainnet swap tests are verified.
- Cross-chain order creation and customer deposits are **disabled**. No working HTTPS order gateway is currently configured; the previous Enzonic URL is intentionally removed.
- Do not send USDT or other assets to a displayed address unless a live order service has been deployed and independently verified.

## Safety requirements before opening swaps or cross-chain orders

1. Verify the deployed bytecode and constructor relationships on the explorer.
2. Confirm the intended pool exists and has the expected token pair and decimals.
3. Add and verify initial liquidity using owner-controlled transactions.
4. Confirm quotes against live reserves and execute a controlled, low-value mainnet swap.
5. For cross-chain orders, deploy a reachable HTTPS gateway, enable finalized deposit watchers, prove inventory and payout controls, and pass end-to-end settlement tests.

No network genesis change is required for these application-layer steps.
