# SOBYA Explorer

Independent, read-only EVM explorer for SOBYA Mainnet. This project is separate from `proof-suite/`; it does not import, modify, or depend on Proof Suite code.

## Live configuration

- Network: SOBYA Mainnet
- EVM chain ID: `357812033857` (`0x534f425941`)
- Native currency: SOBY (18 decimals)
- Read-only RPC: `https://sobya-evm-rpc.nodesafe-dapp.xyz`
- Public URL after GitHub Pages deployment: `https://snforem-cpu.github.io/sobya-chain/explorer/`

## Current capabilities

- Live RPC health and chain-ID verification.
- Latest eight blocks.
- Transaction lookup by hash, including receipt status, sender, recipient, value, gas and fee when returned by the RPC.
- Block lookup with block metadata and up to 40 displayed transactions.
- Address overview with current native balance, transaction count (nonce), and contract bytecode detection.
- Query-string deep links: `?tx=...`, `?address=...`, and `?block=...`.

## Honest scope

This is an RPC-first explorer. It does not yet provide full historical address transaction timelines, token transfer indexing, charts, contract source verification, or internal transaction traces. Those features require a separately operated indexer or additional data service. The interface explicitly avoids presenting unavailable history as an empty or complete history.

## Local checks

Run the unit tests with Node.js:

```sh
node --test explorer/tests/*.test.mjs
```

Open `explorer/index.html` through a local static HTTP server to test browser RPC access. A direct `file://` open may be blocked by browser module security.
