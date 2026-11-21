# SOBYA DEX — Mainnet status

The SOBYA DEX contracts and self-custody interface are deployed/recorded for SOBYA Mainnet. The interface is static and wallet-connected; swaps are intentionally gated until a real, funded market is verified.

## Network
- Network: SOBYA Mainnet
- EVM chain ID: `357812033857`
- Native asset: SOBY (18 decimals)
- RPC: https://sobya-evm-rpc.nodesafe-dapp.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya
- Frontend: https://snforem-cpu.github.io/sobya-chain/dex/

## Recorded mainnet contracts

The four deployment addresses below are recorded in `config.json`. The project owner reported a read-only verification of deployment receipts, deployer, runtime bytecode and constructor links. Re-run the read-only verifier against the connected SOBYA Mainnet provider before relying on these addresses for any new operation.

| Contract | Mainnet address |
|---|---|
| WSOBY | `0x9669a3d516B3423d90F1Ce81eAcF0B363369E09c` |
| Factory | `0x35f59c1Bb30e1FA29020294cB02Bd770D6e3fa8e` |
| TWAP Oracle | `0xb76Aa2fe9459aEF38EB31D687c13D80bCf4716A4` |
| Router | `0x9F3B4AeFbCb937227Dac641Bf7b9e8b42d6CA23D` |

The frontend config is `deploymentStatus: verified` and `liquidityEnabled: true`. `tradingEnabled: false` remains deliberate: a funded pool and controlled live swap tests have not yet been verified. Do not bypass this gate.

## Implemented AMM components

- `SobyaV2Factory`: permissionless pair creation and pair registry.
- `SobyaV2Pair`: LP token, reserve accounting, 0.30% swap fee, liquidity mint/burn, invariant enforcement and cumulative prices.
- `SobyaV2Router`: token swaps, liquidity add/remove, deadline and minimum-output checks.
- `SobyaV2Oracle`: pool-specific TWAP observations with a 30-minute minimum averaging window and 2-hour stale-data rejection.
- `WSOBY`: 1:1 redeemable ERC-20 representation of native SOBY; wrapping does not create new SOBY supply.

## Current liquidity blocker

There is no verified issuer-backed USDT token contract configured on SOBYA Mainnet, and no funded SOBY/USDT pool is currently approved for public trading. USDT contracts on Ethereum, TRON or Solana are not automatically usable on SOBYA: assets and balances do not move between chains merely because they share a symbol.

To establish a genuine SOBY/USDT market, the project needs both:
1. A verified USDT representation deployed/issued for SOBYA, with documented issuer/redemption or bridge backing and an independently verified contract address. Do not label an arbitrary token as USDT.
2. A liquidity provider willing to deposit real SOBY and the quote asset into the pool. The project has discussed a partner-funded liquidity model; no partner capital or pool reserves are represented as present until visible on-chain.

Until those conditions are met, do not create a misleading WSOBY/SOBY self-pair or advertise a price/market that has no independent quote asset.

## Security and operational limits

- A pool TWAP is a reference for that pool only, not a global market price, USD feed, or proof of market-wide value.
- A thin or manipulated pool is not safe collateral pricing. Sensitive applications must compare independent markets and fail closed on stale or unavailable data.
- No official USDT is bundled or represented by these contracts.
- The independent review reported by the project is scoped to the seven named contracts at source commit `81c78793b362d905df9a183580fbc212f7131143`; it does not automatically cover later source changes or deployment configuration.
- Never commit or share a private key or seed phrase.
- Pool creation and funding require explicit wallet signatures and real SOBY gas.
- Public swaps must remain disabled until the funded pool, reserves, token identities, and controlled swaps in both directions are verified on mainnet.

## Build and test

From `contracts/`:
```sh
forge fmt
forge test -vvv
```

No protocol upgrade, genesis change, or paid backend is required for the static DEX architecture.
