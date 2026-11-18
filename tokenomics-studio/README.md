# SOBYA Tokenomics Studio

A free public-good tokenomics planning tool provided by the SOBYA network. It is available to everyone without payment, subscription, account, wallet connection, or license file.

## Features
- Token project setup (name, symbol, total supply, TGE date and forecast horizon)
- Editable allocation table with percentage, TGE unlock, cliff and linear vesting duration
- Monthly unlock schedule and circulating-supply assumption chart
- Rule-based allocation concentration and unlock-pressure indicators
- Save scenarios and compare TGE / month 12 / month 24 outcomes
- Local browser save, JSON export/import, CSV schedule export and print-to-PDF report

## Run
Open `index.html` in a modern browser or publish the folder using GitHub Pages. No build step, package manager, server, RPC, wallet connection, analytics, external API, payment, or third-party JavaScript is required.

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

## Free community commitment
SOBYA Tokenomics Studio is free for everyone. There is no paid tier, license, payment address, transaction submission, or manual license issuance process. The former sales and license-issuer workflow has been retired.
