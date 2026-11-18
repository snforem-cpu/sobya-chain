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

## Payments
This early-access build does not collect payments or verify SOBY transactions. Do not treat a local unlock or browser setting as proof of payment. A payment and license system must be designed separately with a verifiable manual or on-chain verification process before paid access is enabled.
