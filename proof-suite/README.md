# SOBYA Proof — MVP

SOBYA Proof is a simple browser-based tool for recording and verifying document fingerprints on SOBYA Mainnet.

## How it works

1. Choose a document. Your browser calculates its SHA-256 fingerprint locally.
2. Connect your wallet to SOBYA Mainnet.
3. Review and approve one transaction that sends the fixed 1 SOBY service fee to the official SOBYA Proof service wallet and includes the SHA-256 fingerprint in the same transaction data. Payment and fingerprint registration are submitted atomically in the same transaction.
4. Keep the transaction hash. Anyone can use it to verify the record through a SOBYA EVM RPC endpoint.
5. Optionally select a document during verification to compare its fingerprint with the recorded fingerprint.

## Privacy

- The document and its filename are never uploaded by this application.
- Only the SHA-256 fingerprint and the signing wallet address are made public on-chain.
- Each proof costs a separate 1 SOBY service fee, sent to `0xd316993423Fc6268038F4EE3EA7C0C5038513C18` in the same transaction that records the fingerprint.
- The service fee is not a network gas fee. Any gas fee charged by SOBYA is separate and is displayed by the wallet before approval.
- Verification checks the successful transaction, exact 1 SOBY value, service-wallet recipient, SOBYA chain ID, and proof payload.
- Never include confidential or personal information in a document fingerprint workflow unless you are comfortable with the fingerprint being public.

## What the record means

A successful SOBYA Proof record shows that a particular SHA-256 fingerprint was included in a successful SOBYA Mainnet transaction at the recorded block. If a selected file produces the same fingerprint, its bytes match the recorded fingerprint.

The transaction also identifies the wallet address that submitted the record. It does not independently establish the civil identity of the wallet controller, who created a document, whether its contents are true, or who legally owns it.

## Current limitations

- The transaction hash is the proof reference; this MVP uses a paid data-bearing EVM transaction rather than a smart contract or searchable registry. Verification only recognizes transactions matching the exact service-wallet, amount, chain, and proof-data checks.
- Verification depends on access to a configured public SOBYA EVM RPC endpoint.
- A blockchain record proves the fingerprint was recorded; it does not certify the document's contents or confer legal status.
- Invoice Proof, Certificate, and Verify API are separate future products and are not part of this MVP.

## Service fee

- Fixed fee: `1 SOBY` per proof (`1000000000000000000` wei; SOBY has 18 decimals).
- Recipient: `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`.
- The fee amount and proof fingerprint are submitted together in one wallet transaction. Do not send a separate payment.
- Changing the fee or recipient requires updating the app and its verifier together.

## Network configuration

- Network: SOBYA Mainnet
- EVM chain ID: `357812033857` (`0x534f425941`)
- Native currency: SOBY, 18 decimals
- Primary EVM RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- Alternative EVM RPC: `https://sobya-evm-rpc.nodesafe-app.xyz`
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`

## Local tests

Run with Node.js 20 or newer:

```sh
node --test proof-suite/tests/*.test.mjs
node --check proof-suite/app.js
```
