# SOBYA DEX browser quote gateway

This gateway makes the DEX's same-origin quote-preview request reach the
authenticated coordinator without placing the coordinator bearer token in
JavaScript, HTML, browser storage, or a public configuration file.

## Scope and safety

- Exposes exactly one route: `POST /api/cross-chain/v1/quote-previews`.
- Forwards only to the local coordinator's `POST /v1/quote-previews`.
- Injects `SOBYA_COORDINATOR_BEARER_TOKEN` server-side.
- Requires an explicit HTTPS origin allowlist and binds only to loopback.
- Enforces a bounded JSON body and a per-client in-memory rate limit.
- Rejects all other routes and methods. It cannot accept signed quotes, deposits,
  payout proofs, claims, refunds, or transactions.
- Coordinator responses are accepted only when `signed=false` and
  `reserved=false`.

## Required host configuration

The coordinator process must first be constructed with the reviewed
`build_local_server(...)` runtime inputs and started on loopback, for example
`127.0.0.1:8765`. Its quote pricer must read the finalized SOBYA inventory
vault, and its RPC clients, chain identities, observer quorum, readiness
monitor, vault reserver, and signer must be valid production inputs. The
runtime module returns a server object; it does not create those inputs or
start the process automatically.

Start the gateway in a separate supervised process from
`cross-chain/coordinator`:

```sh
export SOBYA_COORDINATOR_URL=http://127.0.0.1:8765
export SOBYA_COORDINATOR_BEARER_TOKEN='<load from local secret store>'
export SOBYA_DEX_ALLOWED_ORIGINS='https://<actual-dex-host>'
export SOBYA_QUOTE_GATEWAY_PORT=8766
PYTHONPATH=.:../observer python browser_gateway.py
```

Do not replace the token with a committed literal. Do not bind either Python
server to a public interface.

## Same-origin reverse proxy

Configure the existing DEX web host to proxy the one API path to the loopback
gateway. Example Nginx location (merge into the existing HTTPS virtual host):

```nginx
location = /api/cross-chain/v1/quote-previews {
    limit_except POST { deny all; }
    client_max_body_size 8k;
    proxy_pass http://127.0.0.1:8766/api/cross-chain/v1/quote-previews;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_connect_timeout 2s;
    proxy_read_timeout 10s;
}
```

The browser calls the same-origin path; it never sees the bearer token. Keep
the coordinator's `/v1` listener inaccessible from the public network.

## Tests

From `cross-chain/coordinator`:

```sh
PYTHONPATH=.:../observer python -m unittest -v test_browser_gateway.py
```

These tests cover the proxy authentication handoff, origin allowlist, route
restriction, schema checks, loopback-only binding, and rate limiting. They are
local integration tests with a fake coordinator, not evidence of live RPC,
funded inventory, source escrow deployments, or a completed cross-chain swap.

## Activation boundary

The DEX cross-chain panel is quote-preview only. The sample chain registry
keeps Ethereum, TRON, and Solana disabled because their USDT token identities,
escrow contracts/program, finality settings, and limits are not yet pinned to
verified deployments. Do not enable a source network or accept user deposits
until its escrow is deployed and independently verified, the coordinator's
observer and attestor configuration is complete, the SOBYA inventory vault is
deployed and funded, and end-to-end refund and payout paths have passed tests.
