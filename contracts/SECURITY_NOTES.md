# WSOBY security test coverage

The Foundry suite includes the following checks:

- Exact 1:1 native-value deposit and ERC-20 minting.
- Burn-before-native-transfer withdrawal and backing invariant.
- Failed native withdrawal to a recipient that rejects native coin; the call must revert without changing the recipient's WSOBY balance, total supply, or backing.
- Re-entrant recipient callback; the callback must not be able to withdraw a second time after the first withdrawal burns the recipient's balance.
- ERC-20 transfer, allowance, and transferFrom accounting.
- 256-run fuzz test for deposit/withdraw round trips.

Run from this directory:

    forge test -vvv

These tests execute in Foundry's local EVM. They do not replace integration tests against the exact SOBYA Cosmos EVM runtime or an independent smart-contract audit. Do not deploy the wrapper or fund a DEX pool based on these tests alone.


## AMM TWAP oracle coverage

The V2 pair now accumulates UQ112x112 reserve prices over elapsed time, and `SobyaV2Oracle` exposes permissionless observations for factory-registered pairs. The oracle enforces a minimum 30-minute observation window and rejects observations older than 2 hours. Tests cover initialization, minimum-window enforcement, equal-reserve quotes, averaging across a reserve-price change, stale observations, and unregistered-pair rejection.

This is only a manipulation-resistant **pool TWAP primitive**. It is not a global market price, a USD feed, or proof that a pool has sufficient liquidity. It must not be used alone for lending collateral, liquidations, minting, or other value-secured actions. Those use cases require independent market sources, liquidity/depth policy, freshness and deviation checks, and fail-closed behavior. No independent smart-contract audit or live SOBYA EVM integration test is claimed.
