# Historical production-genesis preparation record

**SOBYA Mainnet has already been launched.** This file records historical genesis preparation work and must not be used to create, replace, or restart the production network.

Current production identifiers:
- CometBFT chain ID: `sobya-1`
- EVM chain ID: `357812033857`
- Native denomination: `asobya`
- Display symbol: `SOBY` (18 decimals)

Current public endpoints:
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- CometBFT RPC: `https://sobya-rpc.nodesafe-dapp.xyz`
- REST API: `https://sobya-api.nodesafe-dapp.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

The running network's genesis and balances are immutable launch history. Do not use any draft or reconstructed genesis in place of the live chain's genesis. Do not distribute historical draft hashes, proposed allocation commands, or old validator lists as current onboarding instructions.

Additional validators join through the supported live-chain validator-creation transaction after syncing to the existing chain and checking current staking parameters. See [live validator onboarding](validator-support/ONBOARDING.md).

The historical allocation tables and address checks in this file are retained as project records; current account balances and operational parameters must be read from the live network.
