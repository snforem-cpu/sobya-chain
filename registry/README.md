# SOBYA external registry submission bundle

These are preparation files only. No external registry has accepted SOBYA yet.

## Canonical identifiers

- Cosmos chain ID: `sobya-1`
- EVM chain ID: `357812033857` (`0x534f425941`)
- Native asset display name: `SOBYA`
- Native asset symbol: `SOBY`
- Cosmos base denom: `asobya`
- Precision: 18 decimals
- Bech32 account prefix: `sobya`
- SLIP-0044 coin type: 118

## Public endpoints supplied for mainnet

- CometBFT RPC: https://sobya-rpc.nodesafe-app.xyz
- Cosmos REST: https://sobya-api.nodesafe-app.xyz
- EVM JSON-RPC: https://sobya-evm-rpc.nodesafe-app.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya

## Official logo

Use only the project's official crystal-and-gold-ring artwork. The Cosmos Chain Registry contribution must include a square PNG under `sobya/images/` and reference the merged upstream raw URL in both chain and asset metadata. The Keplr contribution also needs its own 256x256 chain image in `images/sobya/chain.png`. The reference copy currently stored in this repository is not a substitute for uploading those assets to the upstream repositories.

## Submission tracks

- **Cosmos Chain Registry:** `registry/cosmos/sobya/chain.json` and `assetlist.json` are prepared. Add the official square PNG at `sobya/images/sobya.png` in the upstream repository. The registry recommends registering the `sobya` Bech32 prefix in SLIP-0173; it describes this as highly recommended, not mandatory.
- **Chainlist:** the contribution file now follows the currently documented path and format: `constants/additionalChainRegistry/chainid-357812033857.js`. Its `icon` field is intentionally omitted until the SOBYA icon is accepted by the icon service. The network entry can be reviewed separately from the icon.
- **Keplr:** a separate Cosmos-SDK integration is required. Its form requires a named node provider and a contact email, plus the image file and detailed Bech32 prefixes. We must obtain the provider's approved public contact email before preparing a complete submission.
- **SLIP-0173:** the proposed `sobya` prefix request is drafted in `external-submissions/SLIP-0173-SOBYA.md`; the maintainers must confirm scope and approve it.

## Verification gates

Before submission, confirm public RPC `/status`, REST `/cosmos/base/tendermint/v1beta1/syncing`, EVM chain ID, and explorer URL templates. Registry CI may remove endpoints that repeatedly fail.

## Safety

This work does not modify Genesis, live chain state, balances, keys, validators, or node configuration. It does not claim acceptance by Chainlist, Cosmos Chain Registry, Keplr, MetaMask, Trust Wallet, or any other wallet.
