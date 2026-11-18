# SOBYA Tokenomics Studio — Sales and licensing

## Published price
- Individual perpetual license: **100 SOBY**
- Scope: one user, one-time payment, perpetual use of the Tokenomics Studio.
- No subscription.

## Current sales status
The public pricing page intentionally states that sales are not open yet. Do not send funds until the owner has:
1. Proven control of the receiving address with a signed message.
2. Independently verified the current SOBYA EVM chain ID and native-token transfer behavior.
3. Published the confirmed receiving address and payment instructions.
4. Installed the license verification public key in the public application.

The configured chain details are EVM chain ID 357812033857, native denomination `asobya`, 18 decimals. The payment must be a native SOBY transfer, not a token with a similar symbol.

## License security design
- Licenses are JSON payloads signed with Ed25519.
- The public application must contain only the public verification key.
- The private signing key is generated and held offline using `license-issuer.html`.
- Never put a private key, mnemonic, or signing secret in this repository, GitHub Actions, browser application source, or chat.
- The issuer signs the payment transaction hash as an audit reference. It does not query the chain and does not establish that payment was received.
- The owner must independently verify chain ID, successful receipt, native transfer amount (100 SOBY = 100 × 10^18 asobya), destination, confirmations, and that the transaction hash has not already been used.
- Maintain a private issuance register to prevent duplicate licenses for one transaction.

## Important limitations
A static browser application cannot provide strong DRM or prevent copying the application source. Signature verification prevents users from inventing valid license files without the private signing key, but does not make the app impossible to modify. The public verification key must be integrated before the app can accept issued licenses.
