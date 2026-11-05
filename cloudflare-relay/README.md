# SOBYA Cloudflare Durable Objects relay (experimental)

This is an experimental transport bridge for the two-validator SOBYA test. It does
not run `sobyad`, store blockchain data, or replace a validator host. Each
validator must still run its own SOBYA/CometBFT process and keep its own home
directory and private validator key.

## Architecture

Each validator's CometBFT process dials a local TCP bridge at
`127.0.0.1:27656`. The Python sidecar converts that TCP stream to an authenticated
WebSocket. The Cloudflare Worker routes both sides to one SQLite-backed Durable
Object, which forwards binary WebSocket messages between roles `a` and `b`.

The relay waits until both sides are connected before sending `READY`. The first
version intentionally supports one active TCP stream per role and is for a
controlled two-validator test only.

## Deploy the Worker

1. Create or use a Cloudflare account with Workers enabled.
2. Install Wrangler locally: `npm install -g wrangler`.
3. From this directory, authenticate: `wrangler login`.
4. Set a long random secret (do not commit it):
   `npx wrangler secret put RELAY_TOKEN`.
5. Deploy:
   `npx wrangler deploy`.
6. Record the deployed Worker URL. Never put the relay token in GitHub source,
   workflow logs, or this repository.

The Worker uses a SQLite-backed Durable Object, which is the backend available
to Workers Free accounts. Free usage is limited; this is a test relay, not a
promise of unlimited 24/7 production bandwidth or compute.

## Run one local bridge side

Install the pinned dependency:

```bash
python3 -m pip install -r requirements.txt
```

Set the same secret on both validator hosts without printing it:

```bash
export SOBYA_RELAY_TOKEN='your-secret'
python3 bridge/relay_client.py --url https://YOUR-WORKER.workers.dev --room sobya-ci-001 --role a
```

On the second host, use the same URL, room and secret, but `--role b`.

Then configure each CometBFT node's `persistent_peers` to the *other* node ID at
`127.0.0.1:27656`. Keep each node's actual P2P listener on its own local
`26656` port. Use the exact node IDs reported by the SOBYA/CometBFT binary; do
not derive or guess them in this relay.

## Security and limitations

- Use a unique high-entropy room name and a strong relay token.
- Keep validator private keys and node keys on their respective validator hosts.
- Do not expose the local bridge listener beyond loopback.
- The relay carries raw P2P bytes; it does not inspect or validate consensus.
- If either side disconnects, the counterpart is closed and CometBFT must retry.
- A passing WebSocket echo test is not proof of CometBFT peer authentication,
  block propagation, consensus, transaction delivery, or production readiness.
- Cloudflare free quotas and platform limits apply. A production chain should not
  depend on one relay object or one provider as its only network path.
