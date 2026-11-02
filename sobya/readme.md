# SOBYA blockchain (development)

SOBYA is a Cosmos SDK application using CometBFT. The repository currently contains a development scaffold, not a launched public network.

## Native token

- Display: `SOBY`
- Base denomination: `asobya`
- Precision: 18 decimals (`1 SOBY = 10^18 asobya`)
- Maximum native supply: `1,000,000,000 SOBY`

The supply cap is represented with arbitrary-precision integer arithmetic. Automatic mint inflation is disabled. The 18-decimal precision is selected to align with EVM gas-token conventions; Cosmos EVM is still a separate integration task and is not yet active in this app. See [TOKENOMICS.md](TOKENOMICS.md).

## Development

Run locally with Ignite:

```sh
ignite chain serve
```

The values in `config.yml` are development-only test allocations. They are not a public launch distribution or final genesis file.

## Safety and status

- This repository branch is for development and verification.
- A successful local build does not prove public-network connectivity, validator independence, or production readiness.
- Do not commit private validator keys, node keys, wallet seed phrases, or other secrets.
- Do not use real funds on this development chain.
