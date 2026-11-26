# SOBYA Proof — MVP

A static, browser-only document fingerprint proof tool for SOBYA Mainnet.

## Current MVP behavior

1. The browser reads a user-selected file locally and computes its SHA-256 digest using Web Crypto.
2. The user connects an EVM wallet and switches to SOBYA Mainnet (EVM chain ID `357812033857`).
3. The wallet signs and broadcasts a zero-value transaction from the connected account to itself. The transaction input contains a versioned SOBYA Proof marker and the 32-byte file digest.
4. Anyone with the transaction hash can read the transaction and receipt from the public SOBYA EVM RPC and verify the record. A verifier may also select a local file to compare its digest.

No file bytes, file name, private key, or wallet secret are uploaded or stored by this application. The signer pays the network fee shown by their wallet. The transaction sender and fingerprint are public.

## Important limitations

- A matching digest proves byte-for-byte correspondence with the digest in the successful transaction; it does not prove authorship, legal ownership, authenticity of the claims inside a document, or the identity of the signer.
- The first release supports document fingerprints only. Invoice Proof, Certificate issuance, and the public Verify API are future phases and are not represented as available features.
- This MVP uses transaction calldata as the public record and does not deploy a smart contract or provide a searchable registry. Keep the transaction hash as the proof reference.
- Verification depends on availability of the configured public RPC endpoints and explorer.
- The app does not upload files or retain a server-side copy.

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
