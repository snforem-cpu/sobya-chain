# SOBYA V2 AMM contracts

This folder contains the SOBYA EVM constant-product AMM source deployed to the recorded SOBYA Mainnet addresses listed in [the DEX status guide](../dex/README.md).

## Components
- `SobyaV2Factory`: permissionless pair creation and pair registry.
- `SobyaV2Pair`: ERC-20 LP token, reserve accounting, 0.30% swap fee, liquidity mint/burn, invariant enforcement, and UQ112x112 cumulative prices.
- `SobyaV2Router`: token-to-token swaps, liquidity add/remove, deadline and minimum-output checks.
- `SobyaV2Oracle`: permissionless TWAP observations for registered pools, with a 30-minute minimum averaging window, two retained checkpoints, and 2-hour stale-data rejection.
- `WSOBY`: 1:1 redeemable wrapper for native SOBY. Users wrap native SOBY before using it in a standard ERC-20 pool.

## Mainnet deployment and release gates

The four contract addresses are recorded in `dex/config.json` and the frontend config marks deployment as verified. The project owner reported a read-only verification of the deployment receipts, deployer, runtime bytecode, and constructor links. This is not a substitute for independently repeating the verifier against the live SOBYA EVM endpoint.

Pool creation/liquidity controls are enabled for owner-controlled initialization. Public swaps remain disabled (`tradingEnabled: false`) until a real quote asset is verified, a pool is funded, reserves are confirmed on-chain, and controlled swap tests pass in both directions.

## Important limitations

- No official Tether USDT contract is bundled or configured on SOBYA Mainnet. Ethereum/TRON/Solana USDT addresses are chain-specific and cannot be used as a SOBYA token address.
- Do not label an arbitrary token or an unbacked wrapped token as USDT. Any SOBYA-side USDT representation requires verifiable issuer/redemption or bridge backing and a reviewed contract identity.
- The 0.30% swap fee remains in pool reserves for liquidity providers; there is no protocol fee recipient or admin fee switch.
- Fee-on-transfer and rebasing tokens are unsupported unless explicitly covered by a separate reviewed integration.
- The TWAP is pool-specific, not a global market price or USD feed. A single thin or manipulated pool is not safe collateral pricing.
- A trustworthy global SOBY price requires multiple independent, liquid external markets or independently operated data providers, robust aggregation, freshness/deviation bounds and outage handling. Do not use this pool's TWAP as a substitute.
- The independent review reported by the project is scoped to seven named contracts at exact source commit `81c78793b362d905df9a183580fbc212f7131143`; it does not automatically cover later source changes, deployment scripts, or configuration.
- Never place a private key or seed phrase in this repository or GitHub Actions.

## Build and test

From this directory:
```sh
forge fmt
forge test -vvv
```

No protocol upgrade, genesis change, or paid backend is required for this architecture.
