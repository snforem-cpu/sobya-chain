# Historical local-testnet and CI reference

**This directory documents local development and historical test environments only. It is not the status page or onboarding guide for SOBYA Mainnet. SOBYA Mainnet is live.**

Production network:
- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- CometBFT RPC: `https://sobya-rpc.nodesafe-dapp.xyz`
- REST API: `https://sobya-api.nodesafe-dapp.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

The local workflows in this directory are retained for reproducible development, regression testing and CI. They may use isolated chain IDs such as `777777`, `777778` or historical testnet identifiers. Those values do not describe the live network and must never be used to configure a production wallet or validator.

A validator joining the existing mainnet must follow [the live validator onboarding guide](../validator-support/ONBOARDING.md). Do not generate a new genesis, submit a genesis gentx, or start a replacement chain to join the running network.

## Local test coverage

The repository's local test workflows cover application behavior, transaction processing, fee routing, validator-reserve logic, EVM JSON-RPC and related integration paths. CI results apply to the commit and workflow run that produced them. They are regression tests; they do not change or host the production network.

## Network safety

Never place validator signing keys, mnemonics, node keys or wallet secrets in source control, workflow logs or CI artifacts. Keep local development data separate from production node homes and wallets.
