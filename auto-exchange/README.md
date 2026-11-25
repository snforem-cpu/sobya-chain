# SOBYA Auto Exchange (isolated)

This directory is a separate project. It must not modify `buy/`, `dex/`, existing contracts, chain configuration, or live balances.

## Agreed commercial policy

- Opening price: 0.005 USDT per SOBY.
- Reference inventory: 1,000,000 SOBY (not a claim about current live balance).
- Exchange fee: 1% (100 bps).
- Upward price coefficient: 1000.
- Downward price coefficient: 250.
- Upward response is four times the downward response.
- Quote validity target: 10 minutes.
- No fixed upper price ceiling.
- Time passing alone never changes price; only confirmed trades/inventory changes may do so.

## Safety status

The interface is informational only. Trading and payouts are disabled. No wallet key, RPC secret, or payment credential belongs in browser code or Git history.

Before enabling settlement, two protocol decisions are required:

1. **Coefficient unit / normalization:** 1000:250 defines the 4:1 direction ratio, but not the absolute price movement per unit of inventory change. Do not silently interpret these as percentages or basis points.
2. **Order-to-deposit binding:** a plain ERC-20 USDT transfer to an externally owned wallet does not contain the quoted SOBY amount, quote ID, or expiry. A settlement worker cannot safely infer which ten-minute quote an untagged transfer belongs to, especially with concurrent deposits or delayed confirmations. A deterministic on-chain order identifier or another audited binding mechanism is required.

The intended deployment target is GitHub Pages; scheduled/dispatch workflows are not always-on servers and cannot use a visitor's MetaMask session. Do not add real payout secrets or enable automated transfers until the above controls, replay protection, durable processed-transaction ledger, confirmations, and inventory checks are implemented and independently tested.

## Tests

Run `npm test` from this directory. The current tests validate the agreed policy and assert that settlement remains disabled.
