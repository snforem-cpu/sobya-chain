# SOBYA Proof — MVP

A static, browser-only document fingerprint proof tool for SOBYA Mainnet.

## Current MVP behavior

1. The browser reads a user-selected file locally and computes its SHA-256 digest using Web Crypto.
2. The user connects an EVM wallet and switches to SOBYA Mainnet (EVM chain ID `357812033857`).
3. The wallet signs and broadcasts a zero-value transaction from the connected account to itself. The transaction input contains a versioned SOBYA Proof marker and the 32-byte file digest.
4. Anyone with the transaction hash can read the transaction and receipt from the public SOBYA EVM RPC and verify the record. A verifier may also select a local file to compare its digest.

No file bytes, file name, private key, or wallet secret are uploaded or stored by this application. The signer pays the network fee shown by their wallet. The signer address and fingerprint are public.

## Evidence levels — do not conflate them

SOBYA Proof is designed to distinguish four separate claims:

1. **Document integrity and timestamp record:** a successful SOBYA transaction records a digest and block position. A matching digest demonstrates that the selected bytes match the recorded digest. The block timestamp is a chain timestamp, not automatically a legally qualified timestamp.
2. **Wallet-signed declaration:** the transaction proves that the controlling wallet signed and submitted this on-chain record. The current MVP does **not** ask the signer to make a separate ownership declaration, and a wallet address is not a verified civil identity.
3. **Verified creator identity:** this requires a trusted identity-verification issuer and a verifiable credential or signed attestation. This is not implemented in the MVP. Identity documents, names, and personal data must not be placed on-chain.
4. **Legal ownership / legal attestation:** a signed ownership claim alone is not conclusive legal title. Where legally required, this layer needs a qualified e-signature provider, notary, registry, or other authorized issuer under the applicable jurisdiction. SOBYA can preserve the associated digest, signatures, and evidence references; it cannot itself confer legal ownership or guarantee court recognition.

The interface must show these as distinct statuses: **Integrity recorded**, **Wallet signer identified by address**, **Creator identity verified (only when an issuer credential is validated)**, and **Legal attestation verified (only when a recognized issuer's evidence is validated)**. Never display identity or legal verification as complete merely because a wallet transaction exists.

## Privacy and security

- Never upload document bytes or filenames.
- Never put names, identity numbers, addresses, or other personal data on-chain.
- Any future ownership declaration must be explicit, shown to the user before signing, and cryptographically bound to the document digest and network context.
- Any future identity integration must validate an issuer's credential or attestation; a self-entered name is not identity verification.
- Do not claim that a blockchain record alone proves authorship, legal ownership, truth of document contents, or civil identity.

## Product roadmap

- **Current phase:** document fingerprint record and public read-only verification.
- **Next phase:** explicit, optional, wallet-signed authorship/ownership declaration bound to the digest, with careful wording that it is a claim by the signer and not independent proof of title.
- **Later phase:** optional issuer-backed identity credentials and jurisdiction-specific legal attestations, only after selecting and validating appropriate issuers and privacy requirements.
- Invoice Proof, Certificate issuance, and Verify API are future products and are not represented as available features in this MVP.

## Current limitations

- This MVP uses transaction calldata as the public record and does not deploy a smart contract or provide a searchable registry. Keep the transaction hash as the proof reference.
- Verification depends on availability of the configured public RPC endpoints and explorer.
- A matching digest proves byte-for-byte correspondence with the digest in the successful transaction; it does not prove authorship, legal ownership, authenticity of the claims inside a document, or the identity of the signer.
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
