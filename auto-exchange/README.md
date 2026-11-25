# SOBYA Auto Exchange (isolated)

This directory is a separate project. It must not modify `buy/`, `dex/`, existing contracts, chain configuration, or live balances.

## Wallet and networks

- Inventory wallet EVM address: `0xebdb899fFE84a89e1d576964b640491c135651AD`.
- Ethereum mainnet (chain ID 1): this address is the destination for customer USDT deposits.
- SOBYA EVM (chain ID 357812033857): the same address is the SOBY inventory/payout wallet.
- The address is identical on both EVM networks, but tokens, balances, transaction hashes, and confirmations are network-specific. USDT deposited on Ethereum is not a SOBY balance on SOBYA.

The address is public and is not a private key. Never store a wallet private key in this file, the frontend, or Git history.

## Agreed commercial policy

- Opening price: 0.005 USDT per SOBY.
- Reference inventory: 1,000,000 SOBY (not a claim about current live balance).
- Exchange fee: 1% (100 bps).
- Upward price coefficient: 1000.
- Downward price coefficient: 250.
- Upward response is four times the downward response.
- Quote validity: 10 minutes.
- No fixed upper price ceiling.
- Time passing alone never changes price; only confirmed trades/inventory changes may do so.

## Settlement design constraints — no paid contract or hosted backend

The owner has explicitly rejected deploying a paid smart contract and adding paid hosting/services. The intended execution environment remains GitHub Pages + GitHub Actions + GitHub Secrets, using public RPC endpoints.

A customer's Ethereum sender address can be read from the USDT transfer and reused as the SOBYA EVM payout recipient. The same address format works across both EVM networks. This solves recipient identification, but it does not by itself bind a deposit to the exact quote shown to the customer.

A plain ERC-20 transfer to this inventory EOA contains only token transfer data (sender, recipient, amount). It does not contain a quote ID, quoted SOBY quantity, or quote expiry. GitHub Actions also cannot read the customer's browser session or local storage. Therefore, do not infer a quote from the sender or deposit amount alone and do not enable automatic payouts until an independently verifiable quote-to-deposit binding and durable replay-protected order ledger exist.

A no-contract/no-paid-hosting design must be proven before accepting funds. In particular, a static GitHub Pages page cannot securely create a private, durable quote record by itself. Any proposed amount-encoding or pre-issued-quote scheme must be specified and tested for collisions, expiry, precision, duplicate transfers, concurrent orders, and price changes. If these requirements cannot be met, the system must remain in quote-only mode rather than risk mispaying customers.

## Safety status

- Trading is disabled.
- Payouts are disabled.
- No private key or signing secret is present in this repository.
- No customer deposits should be sent to this wallet for this Auto Exchange until the full settlement path is implemented, reviewed, and explicitly enabled.

## Tests

Run `npm test` from this directory. Current tests validate the agreed policy and keep settlement disabled.
