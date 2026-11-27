# Cosmos EVM integration — production network

**SOBYA Mainnet is live with Cosmos EVM enabled.** The production EVM chain ID is `357812033857` (`0x534f425941`). The public EVM JSON-RPC endpoint is `https://sobya-evm-rpc.nodesafe-dapp.xyz`.

This document describes the code integration and historical engineering checks. It is not a pre-launch checklist. Local CI fixtures may use chain ID `777777` or `777778`; these are not production identifiers.

## Production EVM access

Use the public EVM JSON-RPC endpoint for MetaMask, Ethereum-compatible wallets, dApps and JSON-RPC clients. Use CometBFT RPC (`https://sobya-rpc.nodesafe-dapp.xyz`) for consensus and node queries. The REST API is `https://sobya-api.nodesafe-dapp.xyz`.

The live application includes Cosmos EVM execution, EVM-aware transaction handling, Ethereum JSON-RPC, fee-market and ERC-20 module integration. EVM chain identity is separate from the CometBFT chain ID `sobya-1`.

## Development and CI

The repository retains local test configurations and smoke tests. Their temporary nodes and test chain IDs are deliberately isolated from Mainnet. A passing or failing local CI run describes that specific source commit and test environment; it does not change the operational status of the already-running network.

## Feature boundaries

Core EVM network operation does not imply that every optional EVM ecosystem feature is deployed. IBC routes, individual token bridges, third-party wallet registries, contract products and external dApps have independent implementation, deployment and verification status. Report those separately and do not describe an optional feature gate as an EVM launch blocker.

## Security

Keep JSON-RPC administrative methods, account unlocking, profiling and debug namespaces disabled on public endpoints. Expose only the required read-only methods through a secured reverse proxy, with TLS, origin restrictions and rate limiting appropriate to the deployment.
