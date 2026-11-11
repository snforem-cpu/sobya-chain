# SOBYA wallet and chain-registry submission bundle

This directory contains draft metadata for external registry submissions. It is not itself an accepted listing.

## Canonical network identifiers

- Cosmos chain ID: `sobya-1`
- EVM chain ID: `357812033857` (`0x534f425941`)
- Native symbol: `SOBY`
- Cosmos base denomination: `asobya`
- Precision: 18 decimals
- Bech32 account prefix: `sobya`
- SLIP-0044 coin type configured in the application: 118

## Current public endpoints supplied for the mainnet

- CometBFT RPC: https://sobya-rpc.nodesafe-app.xyz
- Cosmos REST: https://sobya-api.nodesafe-app.xyz
- EVM JSON-RPC: https://sobya-evm-rpc.nodesafe-app.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya

## Logo

The existing repository asset `assets/logo/sobya-coin-128.png` matches the official SOBYA crystal-and-gold-ring logo. The registry metadata references this stable raw GitHub asset URL.

A 256x256 copy is prepared separately for wallet registries that require that size. Do not claim the external logo has been published until that binary is committed to a public repository and the final raw URL has been checked.

## Submission status and limitations

- Chainlist / ethereum-lists: draft EVM metadata is prepared. Its chain icon metadata requires a publicly retrievable IPFS CID; no CID is included yet, so the network icon portion is not submission-ready.
- Cosmos Chain Registry: draft chain and asset metadata is prepared. Submission still requires review of live endpoint availability and schema/CI validation.
- Keplr: a separate non-native-chain integration request may be required; Cosmos registry inclusion alone does not guarantee automatic enablement.
- MetaMask: Chainlist metadata can simplify manual network addition after acceptance; it does not guarantee automatic addition to every user's wallet or automatic native-token logo display.
- Trust Wallet and other wallets: each has independent asset/network listing policies and review requirements.

No Genesis, chain state, balances, keys, or live-node configuration are modified by these metadata files.
