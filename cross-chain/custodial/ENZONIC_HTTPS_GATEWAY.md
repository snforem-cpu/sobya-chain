# SOBYA public HTTPS gateway on Enzonic

## The two Enzonic endpoints

- Connect upstream supplied by the operator: `fr-one.enzonic.com:25701`, primary port `25701`.
- Public DEX endpoint: a free HTTPS subdomain assigned to the SOBYA gateway Node.js server. The DEX must call this HTTPS subdomain, never the raw Connect host:port.

The gateway source is in `cross-chain/custodial/https-gateway/`. It exposes only the order API paths, allows only the SOBYA DEX browser origin, limits requests to 60/minute per IP and 16 KiB bodies, and authenticates every upstream request and response using HMAC-SHA256 signatures with timestamp and one-time nonce checks. The shared secret is never sent over the network. Only public wallet addresses, quote data and transaction identifiers traverse the upstream connection; wallet keys and seed phrases are never sent to this gateway.

## Enzonic Connect settings

The live local operator config must bind the API to the assigned primary port:

```json
{
  "api": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 25701,
    "allowedOrigin": "https://snforem-cpu.github.io",
    "gatewayTokenEnv": "SOBYA_GATEWAY_TOKEN"
  }
}
```

Set `SOBYA_GATEWAY_TOKEN` in the Enzonic Connect environment as a random secret of at least 64 characters. Do not put it in Git or `config.json`. Set the same value in the gateway server environment. The API verifies request signatures and signs its responses; the gateway rejects unsigned, modified, stale or replayed messages.

The launcher refuses live mode unless:
- Ethereum chain ID 1 and SOBYA EVM chain ID 357812033857 are pinned;
- only Ethereum and SOBYA deposit/payout gates are enabled;
- both networks have HTTPS RPCs, verified balances, encrypted keystore files and passphrase environment variables;
- the Connect API is bound to port 25701 and the shared gateway secret is configured;
- reference liquidity is a positive, independently verified USDT base-unit value;
- pricing, fees, limits and protected SOBY reserve match the approved SOBYA policy.

The default example remains disabled for deposits and payouts.

## Create the public HTTPS gateway

Use Enzonic **Node.js hosting** (not a paid VPS). The official free Node.js tier provides one free server per account, 512 MB RAM, 50% CPU, 10 GB storage and 24/7 uptime without idle hibernation. It provides a free server subdomain; Enzonic's web-hosting documentation describes free subdomains with automatic SSL. Verify the assigned hostname over HTTPS before adding it to the DEX.

Create a free Node.js server in the same Enzonic account and upload/sync the folder:

`cross-chain/custodial/https-gateway/`

Use Node.js 20 or 22 and start command:

`npm start`

The process listens on the Enzonic-provided `PORT` and `0.0.0.0`.

Set these environment variables in the gateway server:
- `SOBYA_UPSTREAM_URL`: use `http://fr-one.enzonic.com:25701` if the Connect primary port serves HTTP, or `https://fr-one.enzonic.com:25701` if it serves trusted TLS. Do not guess the scheme; test the Connect `/health` endpoint first. HMAC authenticates and integrity-protects the upstream messages even if Connect only offers HTTP; that upstream carries public transaction/address data, not secrets.
- `SOBYA_GATEWAY_TOKEN`: the exact same 64+ character secret configured in Enzonic Connect.
- `SOBYA_ALLOWED_ORIGIN`: `https://snforem-cpu.github.io`.

After the server starts, Enzonic shows its assigned free subdomain. Verify:

`https://<assigned-subdomain>/health`

It must return `{"status":"ok","service":"sobya-order-api"}`. Only then set `custodialApiUrl` in `dex/config.json` to that exact HTTPS origin, without a trailing path. Never put `fr-one.enzonic.com:25701` directly in the DEX config.

## Release boundary

This repository prepares the gateway code and launcher, but it cannot create a server inside the user's Enzonic account or know the assigned subdomain. The DEX URL intentionally remains empty until the HTTPS health check succeeds. Do not accept customer deposits until the gateway is live and controlled end-to-end tests pass in both directions.
