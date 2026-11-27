# SOBYA Verify API

A read-only JavaScript verification client for SOBYA Proof and SOBYA Invoice Proof. It reads confirmed transactions from SOBYA Mainnet RPC endpoints and validates the deployed Proof Registry call, exact 1 SOBY service fee, successful receipt, and matching `ProofRecorded` event.

## Important architecture

This is a client-side SDK, not a hosted REST server. GitHub Pages is static hosting and cannot execute server-side API routes. The SDK calls the public SOBYA EVM JSON-RPC endpoints directly. It requires no API key, account, subscription, wallet connection, or transaction signing.

The file and invoice metadata are processed locally. No file, filename, or invoice details are uploaded. The only remote requests are read-only JSON-RPC queries for public blockchain data. The SDK never broadcasts transactions.

## Browser usage

Load the module from the published Proof Suite after deployment:

```js
import { createSobyaVerifyClient } from "./verify-api/client.js";

const sobya = createSobyaVerifyClient();

const result = await sobya.verifyProof({
  txHash: "0xYOUR_TRANSACTION_HASH",
  file: document.querySelector("#file").files[0] // optional
});

console.log(result.valid, result.match, result.fingerprint);
```

For Invoice Proof, provide the original invoice and the same metadata entered at registration:

```js
const result = await sobya.verifyInvoiceProof({
  txHash: "0xYOUR_INVOICE_TRANSACTION_HASH",
  file: invoiceFile,
  metadata: {
    reference: "INV-2026-0042",
    issueDate: "2026-11-27",
    amount: "1250.50",
    currency: "USD",
    issuer: "Supplier",
    recipient: "Customer"
  }
});
```

## Result semantics

- `valid: true`: the transaction is a confirmed, successful SOBYA Proof Registry record that paid exactly 1 SOBY and emitted the matching event.
- `match: true`: the optional file (Proof) or required invoice file plus metadata (Invoice Proof) reproduces the on-chain fingerprint.
- `match: false`: the chain record is valid, but the supplied file or invoice details do not match.
- `match: null`: the chain record is valid; no file comparison was requested.

A rejected transaction throws an Error with a reason. A valid on-chain record does not establish the truth of a document, legal ownership, issuer identity, payment of an invoice, or legal/tax compliance.

## Configuration

The default client uses the two published SOBYA EVM RPC endpoints. A custom list of HTTPS-compatible RPC endpoints can be supplied with `createSobyaVerifyClient({ rpcUrls })`. The client verifies chain ID `357812033857` and the deployed registry address configured in `core.js`.

## Privacy and security

- Read-only; no wallet provider or private key is used.
- No files or invoice fields are sent to a server.
- Uses HTTPS RPC endpoints and validates the chain ID before accepting a result.
- Verifies transaction destination, exact service fee, contract call, successful receipt, submitter/event consistency, and event fingerprint.
- RPC availability and CORS policy remain external dependencies. The SDK tries configured endpoints in order.

## Scope

The first release is a browser-native ES module. It is not an authenticated hosted REST API and does not promise uptime, rate limits, API keys, or a service-level agreement. Those would require separately operated backend infrastructure.
