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

## Supported launch direction

This initial live route is deliberately one-way:

- Ethereum mainnet USDT is the read-only deposit source: `enabled=false`, `depositWatchEnabled=true`, chain ID `1`, canonical USDT contract, HTTPS RPC, and 64 confirmations.
- SOBYA EVM is the payout destination: `enabled=true`, `depositWatchEnabled=false`, chain ID `357812033857`, HTTPS RPC, verified SOBY inventory, and the encrypted SOBYA payout keystore/passphrase.
- An Ethereum signing keystore is not required for this direction. Do not configure an Ethereum payout wallet.
- TRON and Solana remain unsupported for this launch.

The launcher rejects live mode unless the direction-specific watcher and payout configuration, verified SOBYA inventory, positive independently verified reference liquidity, and approved pricing/fee/limit settings are present. It also requires a 64+ character gateway token. Never put secrets in Git or in `config.example.json`.

## Public HTTPS access

Use the free always-on Enzonic Node.js hosting server as the HTTPS gateway. Instructions and source are in [ENZONIC_HTTPS_GATEWAY.md](ENZONIC_HTTPS_GATEWAY.md). The DEX must call the assigned HTTPS subdomain after `/health` succeeds. Do not set `dex/config.json:custodialApiUrl` to the raw Connect host:port.

## API contract

- `GET /health`
- `POST /v1/quotes`
- `GET /v1/orders/{order_id}`
- `POST /v1/orders/{order_id}/deposit`

Quotes are refused until verified reference liquidity is configured and the SOBYA destination's current balance and gas reserve are read from its HTTPS RPC. The SOBYA destination check preserves the 100,000 SOBY reserve. The runtime uses 1% fees, a 500 USDT maximum order and a 10,000 USDT daily Ethereum cap.

A deposit proof is not accepted as paid until the Ethereum watcher independently verifies the exact sender, USDT contract, amount, destination, event index, canonical block and finality. SOBYA payout begins only after finalized deposit verification and completes only after finalized payout verification.

## Release gate

Do not accept customer funds until the public HTTPS gateway is deployed, its health check succeeds, the SOBYA payout balance and gas funding are verified, the Ethereum USDT watcher passes a finalized-deposit test, and a controlled end-to-end USDT-to-SOBY settlement test passes. Keep customer deposits disabled until those checks pass.
