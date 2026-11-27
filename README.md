![SOBYA official logo](assets/logo/sobya-coin-128.png)

# SOBYA Chain

**SOBYA Mainnet is live and publicly accessible.** The production CometBFT network uses chain ID `sobya-1`; the EVM network uses chain ID `357812033857` (`0x534f425941`). The native asset is SOBY (`asobya`, 18 decimals). The public EVM JSON-RPC, CometBFT RPC, REST API and explorer endpoints are listed below.

## Connect to SOBYA Mainnet

| Service | Endpoint |
|---|---|
| EVM JSON-RPC (MetaMask, EVM wallets and dApps) | `https://sobya-evm-rpc.nodesafe-dapp.xyz` |
| CometBFT RPC (consensus and node queries) | `https://sobya-rpc.nodesafe-dapp.xyz` |
| REST API | `https://sobya-api.nodesafe-dapp.xyz` |
| Block explorer | `https://explorer.nodesafe-app.xyz/sobya` |

Use the EVM JSON-RPC endpoint for MetaMask. CometBFT RPC and REST are different protocols and must not be entered as an EVM wallet RPC. If an endpoint is temporarily unavailable, use the explorer or the alternative endpoint officially published by the project; do not infer network failure from one provider URL.

## Network identity and native token

- Network name: **SOBYA Mainnet**
- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`
- Display symbol: `SOBY`
- Base denomination: `asobya`
- Precision: 18 decimals (1 SOBY = 10^18 asobya)
- Maximum native supply: 1,000,000,000 SOBY
- Automatic inflation: disabled under the network's token rules
- Transaction-fee distribution: 50% Treasury, 30% Validators, 20% Community

The values `777777` and `777778` are reserved for local development and CI fixtures only. They are not SOBYA Mainnet identifiers.

## EVM compatibility

SOBYA Mainnet includes the Cosmos EVM execution environment. The public EVM JSON-RPC supports compatible wallets and applications, including Ethereum JSON-RPC methods, signed EVM transactions, native SOBY transfers, smart-contract execution and ERC-20 interactions supported by the deployed network version. Use EVM chain ID `357812033857`; do not use the local CI chain ID.

EVM access is distinct from optional ecosystem features such as IBC routes, third-party wallet listings, token bridges, and individual dApp deployments. Those features must be described according to their own deployment and verification status and do not determine whether the live EVM network is operational.

## SOBYA Proof Suite

The repository includes the published SOBYA Proof Suite:
1. [SOBYA Proof](https://snforem-cpu.github.io/sobya-chain/proof-suite/) — on-chain proof for files and documents.
2. [SOBYA Invoice Proof](https://snforem-cpu.github.io/sobya-chain/proof-suite/) — proof records for commercial invoices.
3. [SOBYA Verify API](https://snforem-cpu.github.io/sobya-chain/proof-suite/verify-api/) — automated verification API for websites and applications.

The former SOBYA Certificate service has been removed and is not part of the current suite.

## SOBYA DEX and other applications

The [SOBYA DEX interface](https://snforem-cpu.github.io/sobya-chain/dex/) is published. The interface, contract deployment state, liquidity and public swap availability are separate from mainnet readiness; consult the DEX documentation for the exact current contract and market status. Do not interpret a DEX feature gate as an EVM or network launch gate.

The [SOBYA Auto Exchange](https://snforem-cpu.github.io/sobya-chain/auto-exchange/) provides the project's exchange workflow and live SOBY price source. [SOBYA Tokenomics Studio](https://snforem-cpu.github.io/sobya-chain/tokenomics-studio/) is a browser-based planning tool.

## Validator participation

SOBYA Mainnet is already running. Additional independent validators can join the existing network through the live-chain validator creation process; they do not participate in a new genesis ceremony and must not create a replacement genesis. Read [Validator Onboarding](docs/validator-support/ONBOARDING.md) and confirm the current binary, sync state, staking parameters, self-delegation requirement, fees and peer details with the project before submitting a live-chain transaction.

Each operator generates and retains their own account, node and validator signing keys. Never send mnemonics, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json` to the project.

## Development and CI

The repository also contains local development networks, automated tests, CI fixtures and tooling. Those environments are isolated from SOBYA Mainnet. A test that uses chain ID `777777` or `777778` is a local test fixture, not a statement that the live network is experimental or unpublished. GitHub Actions runners are temporary build/test machines and are not the production validator host.

## Separate service status

Some optional repository tools and administrative services have their own deployment or security gates. For example, the off-chain validator-support MVP is not the live validator protocol, and DEX public swaps depend on their own liquidity and contract configuration. These limitations must not be conflated with the operational status of SOBYA Mainnet or its EVM.

## Security

Never commit or share mnemonics, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json`. Each operator generates and retains their own keys. Use only verified release binaries and official network endpoints.
