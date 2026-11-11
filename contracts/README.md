# SOBYA EVM native-coin wrapper

## Purpose

SOBYA's native coin remains the Cosmos SDK bank coin with base denomination
asobya and 18 decimal places. EVM accounts can hold and transfer that native
coin as the chain's native EVM balance.

A conventional AMM router expects ERC-20 assets. This repository therefore
introduces WSOBY, a wrapped representation for EVM trading:

- Deposit native SOBY: the same amount of WSOBY is minted.
- Transfer or trade WSOBY as a standard ERC-20.
- Withdraw WSOBY: it is burned before the contract sends the same amount of
  native SOBY back to the caller.
- There is no owner, admin key, premint, arbitrary mint, or arbitrary withdrawal.

The intended invariant is that the contract's native balance is at least
WSOBY totalSupply. The normal deposit/withdraw path keeps the two equal.
Forced native transfers can make backing greater, never less.

## Important distinction

WSOBY is not a second independent SOBY issuance and must not be distributed as
additional tokenomics. It is a redeemable 1:1 representation backed by native
SOBY held in the wrapper contract. A future DEX pool should use the exact
deployed WSOBY contract address and a separately verified quote asset.

Wallets may display the ERC-20 symbol as WSOBY. A wallet or DEX interface may
label it "SOBY (wrapped)" for clarity; it must not misrepresent it as a
separate native balance.

## Deployment status

This change only adds source and CI checks. It does not deploy the contract,
change the live chain, alter genesis, or change the main branch. Production
deployment requires successful tests, review of compiled bytecode, a controlled
deployment transaction on SOBYA mainnet, and publication of the verified
contract address. The address must come from the actual deployment receipt.

## Tests

Run with Foundry from this directory:

    forge fmt --check
    forge test -vvv
