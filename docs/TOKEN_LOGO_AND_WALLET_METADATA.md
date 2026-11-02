# SOBYA Token Logo and Wallet Metadata

## Official mark

The approved SOBYA mark is stored at [assets/logo/sobya-coin-128.png](../assets/logo/sobya-coin-128.png).

## Metadata policy

Keep the token's display name, ticker, base denomination, decimal precision, chain ID, RPC endpoints and logo URI in one canonical network metadata set. Do not publish guessed chain IDs, RPC endpoints, explorer URLs or token contract addresses.

## Wallet compatibility

- EVM wallets (for example MetaMask and Rabby) need a working public EVM JSON-RPC endpoint, the correct EVM chain ID and network metadata. The icon may be sourced from token metadata or a wallet's own registry.
- Cosmos wallets need the chain's Cosmos metadata and supported API endpoints; wallet listing/registry inclusion may be required.
- Trust Wallet and Phantom listing/display behavior must be verified against each wallet's current official submission process. Do not promise universal wallet support.
- The native SOBYA asset and its EVM/ERC-20 representation must not become two independently spendable supplies. The Cosmos EVM integration must use the supported single-asset representation and be tested for conversion/transfer invariants.

## Release gate

Do not announce the logo as visible in a wallet until it has been tested in that wallet. Do not publish production network metadata until the chain ID, public RPC, denom, decimals and explorer are final and operational.
