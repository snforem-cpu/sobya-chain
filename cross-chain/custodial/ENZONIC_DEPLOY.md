# SOBYA Enzonic Connect deployment

Deploy the custodial runtime from the reviewed SOBYA branch. The Python entry point is `cross-chain/custodial/enzonic_start.py`.

## Default startup

- Python 3.12.
- Install `cross-chain/custodial/requirements.txt`.
- Run `python cross-chain/custodial/enzonic_start.py`.
- The example creates a local config with deposit and payout gates disabled. The API is loopback-only for local validation. This does not accept customer deposits.

## Enzonic Connect primary port

The operator supplied Connect address is `fr-one.enzonic.com:25701`, primary port `25701`.

For the live local config set `api.enabled=true`, `api.host=0.0.0.0`, `api.port=25701`, `api.gatewayTokenEnv=SOBYA_GATEWAY_TOKEN`, and `api.allowedOrigin=https://snforem-cpu.github.io`. Set `SOBYA_GATEWAY_TOKEN` as a 64+ character random Enzonic environment secret. The gateway uses HMAC-SHA256 signed requests and responses; the shared secret is not transmitted.

The launcher rejects live mode unless both Ethereum and SOBYA have HTTPS RPCs, existing encrypted keystores, passphrase environment variables, enabled finalized-deposit watchers, independently verified inventories, correct chain IDs, verified reference liquidity, and the approved pricing/fee/limit settings. TRON and Solana are rejected for this launch.

## Public HTTPS access

Use the free always-on Enzonic Node.js hosting server as the HTTPS gateway. Instructions and source are in [ENZONIC_HTTPS_GATEWAY.md](ENZONIC_HTTPS_GATEWAY.md). The DEX must call the assigned HTTPS subdomain after `/health` succeeds. Do not set `dex/config.json:custodialApiUrl` to the raw Connect host:port.

## API contract

- `GET /health`
- `POST /v1/quotes`
- `GET /v1/orders/{order_id}`
- `POST /v1/orders/{order_id}/deposit`

Quotes use completed orders only. A quote is refused until verified reference liquidity is configured and the destination chain's current balance and gas reserve are read from its HTTPS RPC. The SOBYA destination check preserves the 100,000 SOBY reserve. The runtime uses 1% fees, a 500 USDT maximum order and a combined 10,000 USDT daily Ethereum cap across both directions.

A deposit proof is not accepted as paid until the watcher independently verifies the exact sender, asset, amount, destination, event index, canonical block and finality. Payout begins only after finalized deposit verification and completes only after finalized payout verification.

## Release gate

Do not accept customer funds until the public HTTPS gateway is deployed, its health check succeeds, both live inventory balances and gas funding are verified, and controlled end-to-end tests pass in both directions. Keep the DEX API URL empty until the exact public HTTPS origin is known.
