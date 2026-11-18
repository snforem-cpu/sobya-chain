# SOBYA Tokenomics Studio

A static, local-first tokenomics planning tool hosted from GitHub Pages.

## Features
- Token project setup (name, symbol, total supply, TGE date and forecast horizon)
- Editable allocation table with percentage, TGE unlock, cliff and linear vesting duration
- Monthly unlock schedule and circulating-supply assumption chart
- Rule-based allocation concentration and unlock-pressure indicators
- Save scenarios and compare TGE / month 12 / month 24 outcomes
- Local browser save, JSON export/import, CSV schedule export and print-to-PDF report

## Run
Open `index.html` in a modern browser or publish the folder using GitHub Pages. No build step, package manager, server, RPC, wallet connection, analytics, external API or third-party JavaScript is required.

## Calculation model
For each allocation:
- Allocation tokens = total supply × allocation percentage.
- TGE unlocked = allocation tokens × TGE percentage.
- Remaining tokens = allocation tokens − TGE unlocked.
- If vesting duration is zero, the remaining amount is treated as unlocked at TGE.
- Otherwise, no additional amount unlocks until the cliff ends; after the cliff, the remainder unlocks linearly over the vesting duration.
- Modelled unlocked supply is the sum of each allocation's unlocked amount at a selected month.

The tool labels unlocked supply as a circulating-supply assumption. Unlocking does not prove that tokens are transferred, sold, liquid, or economically circulating.

## Privacy and limitations
All calculations run in the browser. The current project and saved scenarios use localStorage on the current device. Export JSON backups to move projects between browsers. Clearing browser storage may delete local saves.

Risk indicators are simplified transparent heuristics, not security audits, legal/tax advice, market forecasts, or investment recommendations.

## Payments and owner license issuance
The public pricing page remains paused until the owner completes a live end-to-end payment test and explicitly opens sales. The owner-only license issuer now checks a submitted transaction against SOBYA Mainnet RPC before signing a license. The private key is used locally in the browser and is never sent to the RPC. It verifies:
- EVM chain ID 357812033857
- transaction and successful receipt exist and match the submitted hash
- native transfer recipient is the configured owner address
- exact transfer value is 100 SOBY (100000000000000000000 asobya)
- plain native transfer (not a contract call)
- receipt recipient and transaction/receipt block consistency
- canonical block hash and at least 3 block confirmations

The RPC query is read-only; it does not connect a wallet, request a signature, or send funds. The issuer signs locally in the browser and the private key is never sent to the RPC. If the browser cannot reach the RPC due to network/CORS restrictions, the issuer must fail closed: do not issue a license until payment is independently verified.

The issuer records transaction hashes and license IDs in that browser's local storage to warn about reuse on that device. This is not a shared or tamper-proof global registry and can be cleared. Global duplicate prevention requires a trusted server-side registry, which is not deployed in this static GitHub Pages version; keep a separate private offline issuance register and manually reconcile each hash before issuing.

## License verification

The public studio includes an offline Ed25519 signature verifier. Import a `.sobya-license.json` file from the **License verification** workspace view. The verifier checks the configured issuer public key, signed canonical payload, product, perpetual individual plan, one-user limit, 100 SOBY price, EVM chain ID `357812033857`, denomination `asobya`, 18 decimals, license ID and transaction-hash format.

The issuer's private key must remain offline and must never be committed or uploaded. The app contains only the public key. A valid signature proves that the file was signed by the matching private key; it does **not** independently verify that a payment occurred, that a transaction hash exists, or that a transaction has not already been used. Payment verification and duplicate-issuance prevention remain manual owner responsibilities. Sales must remain paused until the receiving address and live network/payment procedure are independently confirmed.
