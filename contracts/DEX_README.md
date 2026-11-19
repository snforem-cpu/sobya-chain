# SOBYA V2 AMM contracts

This folder contains a minimal constant-product AMM implementation for SOBYA EVM.

## Components
- `SobyaV2Factory`: permissionless pair creation and pair registry.
- `SobyaV2Pair`: ERC-20 LP token, reserve accounting, 0.30% swap fee, liquidity mint/burn, invariant enforcement, and UQ112x112 cumulative prices.
- `SobyaV2Router`: token-to-token swaps, liquidity add/remove, deadline and minimum-output checks.
- `SobyaV2Oracle`: permissionless TWAP observations for registered pools, with a 30-minute minimum averaging window, two retained checkpoints, and 2-hour stale-data rejection.
- `WSOBY`: separate native SOBY wrapper already in this repository. To trade native SOBY in an ERC-20 pool, users first wrap it into the verified WSOBY deployment.

## Important limitations
This is a first implementation for review and test, not an audited production exchange.
- No native-coin router entrypoints: wrap native SOBY into WSOBY first.
- No protocol fee recipient or admin fee switch. The 0.30% swap fee remains in pool reserves for liquidity providers.
- No fee-on-transfer/rebasing token support. Use ordinary ERC-20 assets only.
- The TWAP is a pool-specific reference, not a global market price or USD feed. A single thin or manipulated pool is not safe collateral pricing. Applications must assess liquidity depth and compare independent markets; stale or unavailable TWAPs must cause sensitive actions to fail closed.
- A public update retains the preceding checkpoint so an updater cannot continually reset the only usable averaging window. This does not remove low-liquidity, quote-asset, or market-manipulation risk.
- The factory deploys pair contracts with CREATE (not CREATE2); router resolves pairs through the factory registry, avoiding hard-coded init-code hashes.
- No USDT is bundled or represented. A stablecoin pool must use a separately verified, issuer-backed token contract.
- Independent audit and exact SOBYA EVM runtime tests are required before mainnet deployment or public funds.

## Global price is not implemented

A trustworthy global SOBY price cannot be derived from this DEX's own pool alone. It requires multiple independent, liquid external markets or independently operated data providers, a documented asset/quote mapping, source-quality and liquidity thresholds, robust aggregation, freshness and deviation limits, outage handling, and independent on-chain reporters or a verifiable feed. No verified external SOBY market/feed addresses or operational reporter set are currently configured in this repository. Therefore this implementation deliberately does not publish a fabricated global or USD price. Do not use its TWAP as a substitute.

## Build and test
From this directory, with Foundry installed:
```sh
forge fmt
forge test -vvv
```

## Deployment
Deploy WSOBY, Factory, Oracle(factory), then Router(factory, WSOBY) using a controlled wallet on SOBYA EVM. The owner must retain deployment transaction hashes and actual contract addresses. Never place a private key or seed phrase in this repository or GitHub Actions. Do not set frontend configuration from guessed addresses.
