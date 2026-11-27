# SOBYA Invoice Proof

Phase 2 of the SOBYA Proof Suite. This page creates a private SHA-256 fingerprint binding the invoice file to its reference, issue date, total, currency and optional issuer/recipient fields.

## Privacy model

- Invoice bytes and all entered invoice fields are processed locally in the browser.
- No invoice file, filename, invoice number, amount, currency, date or party name is uploaded or written on-chain.
- The chain receives only the final SHA-256 digest through the existing SOBYA Proof Registry, plus the public submitting wallet and block timestamp.
- The digest is domain-separated with `SOBYA_INVOICE_PROOF` and versioned, so it cannot be confused with a plain document fingerprint.
- Verification requires the original invoice file and the exact same invoice fields used during registration.

## Network and fee

- SOBYA Mainnet EVM chain ID: `357812033857`.
- Existing registry: `0x9B1C6Cc504DEb8FA7aB9DAe499aB3D042fEC97b9`.
- Existing official service recipient: `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`.
- Service fee: exactly `1 SOBY` per invoice proof. Network gas is separate and shown by MetaMask.
- This phase reuses the already deployed `recordProof(bytes32)` function. No contract redeployment, chain upgrade, genesis change or validator action is required.

## Evidence limits

A matching proof establishes that the selected file and supplied invoice metadata reproduce the digest registered in a successful SOBYA Mainnet transaction. It does not prove that an invoice was paid, goods were delivered, the issuer is genuine, tax rules were met, or the invoice has legal validity.

## Tests

Run:

```sh
node --test proof-suite/invoice-proof/tests/*.test.mjs
node --check proof-suite/invoice-proof/app.js
```
