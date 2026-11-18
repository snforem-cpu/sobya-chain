# SOBYA V2 AMM contracts

This folder contains a minimal constant-product AMM implementation for SOBYA EVM.

## Components
- `SobyaV2Factory`: permissionless pair creation and pair registry.
- `SobyaV2Pair`: ERC-20 LP token, reserve accounting, 0.30% swap fee, liquidity mint/burn and invariant enforcement.
- `SobyaV2Router`: token-to-token swaps, liquidity add/remove, deadline and minimum-output checks.
- `WSOBY`: separate native SOBY wrapper already in this repository. To trade native SOBY in an ERC-20 pool, users first wrap it into the verified WSOBY deployment.

## Important limitations
This is a first implementation for review and test, not an audited production exchange.
- No native-coin router entrypoints: wrap native SOBY into WSOBY first.
- No protocol fee recipient or admin fee switch. The 0.30% swap fee remains in pool reserves for liquidity providers.
- No fee-on-transfer/rebasing token support. Use ordinary ERC-20 assets only.
- No oracle or price-feed guarantee. Pool spot prices are manipulable and must not be used as an oracle.
- The factory deploys pair contracts with CREATE (not CREATE2); router resolves pairs through the factory registry, avoiding hard-coded init-code hashes.
- No USDT is bundled or represented. A stablecoin pool must use a separately verified, issuer-backed token contract.
- Audit and exact SOBYA EVM runtime tests are required before mainnet deployment or public funds.

## Build and test
From this directory, with Foundry installed:
```sh
forge fmt
forge test -vvv
```

## Deployment
Deploy WSOBY, Factory, then Router(factory, WSOBY) using a controlled wallet on SOBYA EVM. The owner must retain deployment transaction hashes and actual contract addresses. Never place a private key or seed phrase in this repository or GitHub Actions. Do not set frontend configuration from guessed addresses.
