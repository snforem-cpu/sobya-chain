# Proposed SLIP-0173 entry for SOBYA

## Requested table entry

| Coin | Mainnet | Testnet | Regtest |
| --- | --- | --- | --- |
| SOBYA | `sobya` | | |

## Project details for the proposal

- Project: SOBYA
- Mainnet chain ID: `sobya-1`
- Address human-readable prefix: `sobya`
- Public source repository: https://github.com/snforem-cpu/sobya-chain
- Native asset: SOBY
- EVM chain ID: `357812033857`

## Rationale

SOBYA is a live Cosmos SDK / CometBFT network using Bech32 account addresses with the `sobya` human-readable prefix. Registering the prefix helps reduce ambiguity and improves interoperability with tools that consult the SLIP-0173 registry.

## Important scope note

SLIP-0173 is titled for BIP-0173 human-readable parts and its primary table is for SegWit-compatible witness programs. Cosmos Chain Registry recommends registering chain Bech32 prefixes there, but describes this as highly recommended rather than mandatory. The maintainers should confirm whether this Cosmos account prefix is in scope for their registry.

## Submission status

This is a prepared proposal only. No branch or pull request has been created in satoshilabs/slips because the connected GitHub integration returned HTTP 403 (Resource not accessible by integration) when attempting to create a branch in that upstream repository.
