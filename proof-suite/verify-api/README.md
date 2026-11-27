# SOBYA Verify API

A read-only HTTP API and browser verification tool for SOBYA Proof and Invoice Proof on SOBYA Mainnet.

## Try it

Open the Verify API page in the SOBYA Proof Suite. It lets a person paste a transaction hash, select the original file, and see whether the on-chain record is valid and whether the file matches. Invoice checks additionally require the same invoice metadata entered during registration. Files are fingerprinted locally and are never uploaded.

## Hosted API routes

- `GET /v1/health` — service/network status.
- `POST /v1/verify/proof` — verify a document proof.
- `POST /v1/verify/invoice` — verify an invoice proof using the original file fingerprint and exact metadata used at registration.

### Document proof

The caller computes SHA-256 locally and sends only the fingerprint (never the file):

```http
POST /v1/verify/proof
Content-Type: application/json

{"txHash":"0x…","fileHash":"0x…"}
```

`fileHash` is optional. Without it, the API validates the on-chain record and returns `match: null`.

### Invoice proof

```json
{
  "txHash": "0x…",
  "fileHash": "0x…",
  "metadata": {
    "reference": "INV-2026-0042",
    "issueDate": "2026-11-27",
    "amount": "1250.50",
    "currency": "USD",
    "issuer": "Supplier",
    "recipient": "Customer"
  }
}
```

### Response

Success returns `{ ok: true, result: { valid, match, type, txHash, fingerprint, signer, blockNumber, timestamp, chainId, registry, feeRecipient } }`.

`valid` means the transaction is a confirmed registry record with the expected contract, service recipient, 1 SOBY fee and matching event. `match` means the supplied fingerprint (and invoice metadata) matches the recorded fingerprint. It does not prove document truth, legal ownership, issuer identity, invoice payment or legal/tax compliance.

Errors use `{ "ok": false, "error": { "message": "..." } }` with HTTP status codes.

## Privacy and limits

- Files and filenames are never uploaded. Only a transaction hash, SHA-256 fingerprint and (for invoices) invoice metadata are sent.
- No wallet connection, signing, write transaction, or API secret is required.
- This is a public beta endpoint. It currently has no API-key system, usage dashboard, SLA, or per-customer quota. Do not advertise paid plans or production SLAs until abuse controls and monitoring are added.
- CORS is open for public read-only integration. Request bodies are limited to 16 KB. RPC provider availability remains an external dependency.

## Deploy to Cloudflare Workers (free tier)

1. Create a Cloudflare account and a Workers API token with permission to edit Workers.
2. Add repository Actions secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
3. Run the **Deploy SOBYA Verify API** workflow from GitHub Actions, or deploy manually from this directory with `npm install` then `npx wrangler deploy`.
4. Cloudflare assigns a `workers.dev` URL. Confirm `/v1/health` responds with chain ID `357812033857` before publishing that endpoint as the hosted API base URL.

GitHub Pages hosts the interface and documentation; Cloudflare Workers runs the HTTP API. No paid domain is required. The hosted endpoint is not live until a Cloudflare account is connected and the deployment workflow succeeds.
