# SOBYA Enzonic Connect deployment

Deploy the custodial runtime from branch `feat/sobya-live-order-clean` only after reviewing its pull request. The Python entry point is `cross-chain/custodial/enzonic_start.py`.

## Default startup

- Python 3.12.
- Install `cross-chain/custodial/requirements.txt`.
- Run `python cross-chain/custodial/enzonic_start.py`.
- The example creates a local config with deposit and payout gates disabled. The order API is enabled only on loopback for local validation. This does not accept customer deposits.

## Enzonic Connect primary port

The assigned public Connect address supplied by the operator is `fr-one.enzonic.com:25701`, primary port `25701`.

For live mode, the local operator config must set:

- `api.enabled=true`
- `api.host=0.0.0.0`
- `api.port=25701`
- `api.gatewayTokenEnv=SOBYA_GATEWAY_TOKEN`
- `api.allowedOrigin=https://snforem-cpu.github.io`

Set `SOBYA_GATEWAY_TOKEN` as an Enzonic Connect secret/environment variable, not in Git or in the JSON config. The same secret is configured in the separate HTTPS gateway. The API rejects public requests without the matching gateway token.

The launcher refuses live mode unless both Ethereum and SOBYA have HTTPS RPC environment variables, existing encrypted keystore files, passphrase environment variables, enabled finalized-deposit watchers, independently verified inventories, and a non-zero verified reference-liquidity value. TRON and Solana are rejected for this launch.

## Public HTTPS access

The Connect host:port is the upstream service address, not a verified HTTPS URL. Use the separate Enzonic Deploy reverse proxy described in [ENZONIC_HTTPS_GATEWAY.md](ENZONIC_HTTPS_GATEWAY.md). The DEX must call only the HTTPS hostname assigned by Enzonic Deploy after its `/health` endpoint has been verified. Do not set `dex/config.json:custodialApiUrl` to the raw Connect address.

## API contract

- `GET /health`
- `POST /v1/quotes`
- `GET /v1/orders/{order_id}`
- `POST /v1/orders/{order_id}/deposit`

Quotes are derived from completed ledger orders only. A quote is refused until verified reference liquidity is configured and the destination chain's current balance is read from its HTTPS RPC. The SOBYA destination check preserves the 100,000 SOBY reserve. The runtime uses 1% fees, a 500 USDT maximum order, and a 10,000 USDT daily cap.

A deposit proof is not accepted as paid until the watcher independently verifies the exact sender, token/native asset, amount, destination, event index, canonical block and finality. Payout begins only after finalized deposit verification and completes only after finalized payout verification.

## Release gate

The code and gateway project are not a substitute for operator deployment. Do not accept customer funds until the HTTPS gateway is deployed, its public health check succeeds, both live inventory balances and gas funding are verified, and controlled end-to-end tests pass in both directions. Keep the DEX API URL empty until the exact public HTTPS origin is known.
