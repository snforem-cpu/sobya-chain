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
