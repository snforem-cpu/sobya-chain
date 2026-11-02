# SOBYA blockchain (development)

SOBYA is a Cosmos SDK application using CometBFT. The repository currently contains a development scaffold, not a launched public network.

## Native token

- Display: `SOBY`
- Base denomination: `usobya`
- Precision: 6 decimals (`1 SOBY = 1,000,000 usobya`)
- Maximum native supply: `1,000,000,000 SOBY`

The application validates the native genesis allocation against this cap. Automatic mint inflation is disabled: the mint module stays in the required block order, but its genesis parameters and current inflation are forced to zero. See [TOKENOMICS.md](TOKENOMICS.md) for the current rules and decisions still pending.

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
