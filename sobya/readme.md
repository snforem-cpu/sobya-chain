# SOBYA blockchain — Mainnet

**SOBYA Mainnet is live.** This repository contains the Cosmos SDK / CometBFT application and Cosmos EVM execution environment used by the production network.

## Production network

- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`
- Network name: `SOBYA Mainnet`
- Native display asset: `SOBY`
- Native base denomination: `asobya`
- Precision: 18 decimals
- Maximum native supply: 1,000,000,000 SOBY
- Automatic mint inflation: disabled under the network token rules.

Public endpoints:
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- CometBFT RPC: `https://sobya-rpc.nodesafe-dapp.xyz`
- REST API: `https://sobya-api.nodesafe-dapp.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

Use the EVM JSON-RPC endpoint for MetaMask and EVM applications. CometBFT RPC and REST serve different protocols.

## EVM and fee routing

The production application includes Cosmos EVM, EVM JSON-RPC execution, ERC-20 and fee-market modules, EVM-aware transaction handling, and unified EVM/Cosmos transaction processing. Mainnet EVM chain ID is `357812033857`. Local development and CI fixtures may use `777777` or `777778`; those values are not production network IDs.

The agreed network transaction-fee distribution is 50% Treasury, 30% Validators and 20% Community. The shared on-chain management destination may aggregate Treasury and Community transfers; their accounting categories remain separate in the project's allocation ledger.

## Local development

Run local disposable development environments with Ignite:

```sh
ignite chain serve
```

Localnet configuration and CI fixtures are not production genesis or production network endpoints. Never connect a production wallet to a local test chain or confuse a CI chain ID with the mainnet EVM chain ID.

## Operational distinction

SOBYA Mainnet and its EVM are live. Individual optional features—such as particular IBC routes, third-party listings, independently deployed dApps, and local developer tooling—have their own feature and verification status. A limitation in one optional feature does not mean the chain or EVM is not launched.

Never commit private validator keys, node keys, mnemonics, or wallet secrets.
