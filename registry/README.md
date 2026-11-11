# SOBYA external registry submission bundle

These are draft contributions prepared for review by the official external registries. They are not accepted listings.

## Canonical identifiers

- Cosmos chain ID: `sobya-1`
- EVM chain ID: `357812033857` (`0x534f425941`)
- Native asset: `SOBY`
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

Use only the supplied SOBYA crystal-and-gold-ring artwork. The Cosmos registry metadata references the intended final path:
`https://raw.githubusercontent.com/cosmos/chain-registry/master/sobya/images/sobya.png`

That URL will not exist until the logo is added and the upstream contribution is merged. The original binary logo is prepared separately at 256x256 and 512x512.

## Submission gates

- Chainlist: EVM metadata is prepared at `_data/chains/eip155-357812033857.json`. No icon is declared yet because its icon registry requires a publicly retrievable IPFS CID and explicitly discourages Pinata. Add the `icon` field and `_data/icons/sobya.json` only after a compliant CID is available.
- Cosmos Chain Registry: contribution structure is `sobya/chain.json`, `sobya/assetlist.json`, and `sobya/images/sobya.png`. The `sobya` Bech32 prefix may require SLIP-0173 registration; this must be confirmed before submission.
- Keplr: requires a separate community-driven integration contribution and validation; Cosmos registry acceptance does not guarantee Keplr integration.
- No changes to Genesis, live chain state, balances, keys, validators, or node configuration are part of this metadata work.
