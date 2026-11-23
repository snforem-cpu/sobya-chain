# SOBYA public HTTPS route for Enzonic Connect

## What the two Enzonic addresses do

- Enzonic Connect primary address: `fr-one.enzonic.com:25701`. This is the upstream host and port supplied for the running SOBYA process. A host:port alone does not prove whether the upstream protocol is HTTP or HTTPS.
- Enzonic Deploy gateway: Enzonic Deploy supplies a public project hostname with managed HTTPS. The DEX must call that HTTPS hostname, not the raw Connect host:port.

The gateway source is in `cross-chain/custodial/https-gateway/`. It is a small Node.js reverse proxy with:
- strict upstream host/port allowlisting (only `fr-one.enzonic.com:25701`);
- only the order API paths (`/health`, quote, order status, deposit proof);
- browser-origin allowlisting;
- 60 requests/minute per client IP and a 16 KiB body limit;
- a shared gateway token injected server-to-server and never exposed to the browser;
- no wallet keys, RPC credentials, or signing operations.

## Enzonic Connect process settings

The local operator config used by `enzonic_start.py` must keep the order API enabled and bind it to the assigned primary port:

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

Keep the API token in Enzonic Connect environment variables, not in Git or `config.json`. Set `SOBYA_GATEWAY_TOKEN` to a long random secret (at least 32 random bytes). The launcher rejects live mode if the token, HTTPS RPCs, encrypted keystores, verified inventories, both chain watchers, or verified reference liquidity are missing. The default example remains disabled.

The live operator config must enable only Ethereum and SOBYA:
- Ethereum chain ID 1, USDT contract pinned in the example, HTTPS RPC, verified USDT inventory, deposit watcher, encrypted keystore and passphrase env.
- SOBYA EVM chain ID 357812033857, HTTPS RPC, verified SOBY balance, deposit watcher, encrypted keystore and passphrase env.
- `featureEnabled=true`, global `depositWatchEnabled=true`, and per-network `enabled=true` and `depositWatchEnabled=true`.
- `referenceLiquidityUsdtBaseUnits` must be the independently verified executable liquidity value in USDT's 6-decimal base units. Do not copy an estimate or invent it.
- Keep the protected SOBY reserve at 100,000 SOBY.

## Enzonic Deploy gateway

Create a free Enzonic Deploy project from this same GitHub repository and branch. Set its root directory to:

`cross-chain/custodial/https-gateway`

Use Node.js 20 or later and start command:

`node server.mjs`

Set these server-side environment variables in the Deploy project:
- `SOBYA_UPSTREAM_URL`: the verified upstream URL for the Connect host, using `https://fr-one.enzonic.com:25701` only if that primary port presents a valid trusted TLS certificate. The gateway intentionally rejects plain HTTP upstreams because the shared authentication token must not travel unencrypted. If Connect does not provide TLS on port 25701, do not use this proxy configuration yet; a TLS-enabled upstream endpoint or secure private tunnel must be enabled first.
- `SOBYA_GATEWAY_TOKEN`: the exact same secret configured in Enzonic Connect.
- `SOBYA_ALLOWED_ORIGIN`: `https://snforem-cpu.github.io`.

After deployment, Enzonic Deploy assigns the project a public HTTPS hostname and manages its certificate. Verify that hostname's `/health` returns `{"status":"ok","service":"sobya-order-api"}`. Only then set `custodialApiUrl` in `dex/config.json` to the exact HTTPS origin (no trailing path). Do not put the Connect address in the DEX config.

## Important deployment boundary

This repository change prepares the gateway; it does not create the Enzonic Deploy project or assign its hostname because that requires an action in the Enzonic account dashboard. Enzonic Connect's primary port is not, by itself, proof of a public TLS certificate. Do not accept customer deposits until both the gateway health check and controlled end-to-end deposit/payout tests succeed. If Enzonic's free Deploy server sleeps when idle, the first request after idle may be delayed; test this before enabling live orders.
