# SOBYA Cosmos EVM Integration

Status: **EVM runtime is integrated in the current `main` source and the public mainnet EVM JSON-RPC passed external read-only checks on 2026-11-11.** This confirms the live EVM read path and wallet balance queries. A live mainnet signed transaction has not been broadcast as part of this preflight.

## Current main source integration

The current `main` source contains:

- EVM, FeeMarket, and ERC-20 stores and keepers.
- Manual runtime module registration compatible with SOBYA's existing depinject-based application.
- Cosmos EVM ante-handler installation for Ethereum and Cosmos transactions.
- Unified EVM/Cosmos mempool and proposal/check-tx handling.
- Cosmos EVM server startup command registration, including the EVM JSON-RPC server path.
- EVM account codec and keyring interface registration.
- Native coin metadata configured as SOBY / asobya with 18 decimals.

The production network identifiers are distinct:

- CometBFT chain ID: `sobya-1`.
- EVM chain ID: decimal `357812033857`, hexadecimal `0x534f425941`.
- Development EVM ID `777777` is not the production ID.

## External live-mainnet read-only verification — 2026-11-11

The following checks were made from an external GitHub-hosted runner against the endpoints supplied by NodeSafe:

- CometBFT RPC reported `sobya-1` and advancing blocks.
- EVM `eth_chainId` returned `0x534f425941`.
- EVM `eth_blockNumber` returned a non-zero block height.
- EVM `eth_getBalance` returned valid balances for both published owner wallet addresses:
  - Founder wallet: 400,000,000 SOBY.
  - Shared wallet: 450,000,000 SOBY.

This verifies that the public EVM JSON-RPC is responding on the intended production chain and can read the two genesis wallet balances. It does not prove MetaMask transaction signing, successful live transaction inclusion, or continuous endpoint availability.

## Local EVM runtime CI evidence

GitHub Actions run [41759772406](https://github.com/snforem-cpu/sobya-chain/actions/runs/41759772406) completed successfully on the separate `feature/cosmos-evm-logo-audit` branch on 2026-11-04. Its local EVM test node passed:

- `eth_chainId`, `net_version`, and `eth_blockNumber`.
- A signed Ethereum transaction.
- Solidity contract deployment and read/write.
- ERC-20 deployment, metadata, supply, and transfer.
- WebSocket new-block subscription.

This is useful runtime evidence for that tested feature-branch commit. It must not be represented as a signed transaction test against the currently running mainnet binary.

## MetaMask network settings

Use these values to add SOBYA Mainnet as a custom network:

| Setting | Value |
|---|---|
| Network name | SOBYA Mainnet |
| RPC URL | `https://sobya-evm-rpc.nodesafe-app.xyz` |
| Chain ID | `357812033857` |
| Currency symbol | `SOBY` |
| Block explorer | `https://explorer.nodesafe-app.xyz/sobya` |

The live balance query confirms the wallet read path. Before sending a transaction, independently verify current EVM gas price/fee behavior and nonce, and obtain explicit transaction approval from the wallet owner. The external preflight did not sign or broadcast a transaction.

## Token invariants

- Native token: SOBY; base denomination: `asobya`.
- Precision: 18 decimal places.
- Maximum supply: 1,000,000,000 SOBY = 10^27 `asobya`, enforced with arbitrary-precision integers.
- Founder allocation: 40% (400 million SOBY).
- Network fee allocation target: 50% treasury, 30% validators, 20% community. This is separate from initial token allocation; do not claim custom fee routing is live unless separately verified on-chain.
- Do not invent allocations for the remaining initial supply or imply exchange listings.

MetaMask compatibility is verified for network identification and balance reads. Do not claim Trust Wallet or Phantom compatibility without their own network/token requirements and tests.

## Remaining production checks

- Test a controlled signed mainnet EVM transaction only after the owner approves the exact transaction and current fee parameters are verified.
- Independently monitor endpoint availability and RPC security configuration.
- Verify fee-routing behavior on-chain before describing the 50/30/20 fee split as operational.
