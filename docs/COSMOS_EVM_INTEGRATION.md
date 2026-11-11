# SOBYA Cosmos EVM Integration

Status: **EVM runtime is integrated in the `v0.1.0-rc.2` release and the public mainnet EVM JSON-RPC passed external read-only checks on 2026-11-11.** Network identification and balance reads work. The live fee quote currently returns zero, so do not send a MetaMask transaction until the fee policy is confirmed.

## Current runtime integration

The released source contains:

- EVM, FeeMarket, and ERC-20 stores and keepers.
- Manual runtime module registration compatible with SOBYA's depinject-based application.
- Cosmos EVM ante-handler installation for Ethereum and Cosmos transactions.
- Unified EVM/Cosmos mempool and proposal/check-tx handling.
- Cosmos EVM server startup command registration, including the EVM JSON-RPC server path.
- EVM account codec and keyring interface registration.
- Consensus fee-router installation. It routes the treasury and community portions to the shared management wallet and leaves the validator portion for the standard distribution module.

The `v0.1.0-rc.2` tag points to source commit `90512106ee2f3c2a38c8f5bab66edc17688fba43`. The release is marked prerelease. Its published Linux package assets have GitHub SHA-256 digests:
- amd64: `d444eb52dc5c936474770bbe42dcfea61f36ec8aa4ac06b957340212ef24251b`
- arm64: `7d44d7f5389d1c1d00c8d737b0699cb5bbab1cce1ebb26b02afd87dafe8d4800`

Release page: https://github.com/snforem-cpu/sobya-chain/releases/tag/v0.1.0-rc.2

Production network identifiers:

- CometBFT chain ID: `sobya-1`.
- EVM chain ID: decimal `357812033857`, hexadecimal `0x534f425941`.
- Development EVM ID `777777` is not the production ID.

## External live-mainnet read-only verification — 2026-11-11

The following checks were made from external GitHub-hosted runners against the endpoints supplied by NodeSafe:

- CometBFT RPC reported `sobya-1`, the expected Node ID, and advancing blocks.
- EVM `eth_chainId` returned `0x534f425941`.
- EVM `eth_blockNumber` returned a non-zero block height.
- EVM `eth_getBalance` returned valid balances for both published owner wallet addresses:
  - Founder wallet: 400,000,000 SOBY.
  - Shared wallet: 450,000,000 SOBY.
- `eth_getTransactionCount` returned founder nonce 0.
- `eth_estimateGas` returned `0x5208` (21,000 gas) for a zero-value native transfer estimate.

**Fee warning:** at the time of the external check, `eth_gasPrice` and `eth_maxPriorityFeePerGas` both returned `0x0`. `eth_feeHistory` also returned zero base-fee and reward values for the sampled blocks. The attempted REST fee-market queries returned HTTP 501. This does not by itself prove that all live transactions are free, but it means the RPC is not currently advertising a positive EVM fee quote. The 50/30/20 fee router code exists in the release, but no paid live-mainnet transaction has been used to prove the fee split. Confirm the live fee-market parameters and minimum accepted EVM fee with NodeSafe before sending transactions.

The read-only checks prove that the public EVM JSON-RPC is responding on the intended production chain and can read the two genesis wallet balances. They do not prove live transaction inclusion or continuous endpoint availability.

## Local EVM runtime CI evidence

GitHub Actions run [41759772406](https://github.com/snforem-cpu/sobya-chain/actions/runs/41759772406) completed successfully on the separate `feature/cosmos-evm-logo-audit` branch on 2026-11-04. Its local EVM test node passed:

- `eth_chainId`, `net_version`, and `eth_blockNumber`.
- A signed Ethereum transaction.
- Solidity contract deployment and read/write.
- ERC-20 deployment, metadata, supply, and transfer.
- WebSocket new-block subscription.

This is runtime evidence for that tested feature-branch commit. It is not a signed transaction test against the currently running mainnet.

## MetaMask network settings

Use these values to add SOBYA Mainnet as a custom network:

| Setting | Value |
|---|---|
| Network name | SOBYA Mainnet |
| RPC URL | `https://sobya-evm-rpc.nodesafe-app.xyz` |
| Chain ID | `357812033857` |
| Currency symbol | `SOBY` |
| Block explorer | `https://explorer.nodesafe-app.xyz/sobya` |

MetaMask can use the endpoint to identify the network and read balances. Do not send a transaction until NodeSafe confirms the intended EVM gas/fee settings and the team verifies the on-chain fee behavior. The external preflight did not sign or broadcast a transaction.

## Token invariants

- Native token: SOBY; base denomination: `asobya`.
- Precision: 18 decimal places.
- Maximum supply: 1,000,000,000 SOBY = 10^27 `asobya`, enforced with arbitrary-precision integers.
- Founder allocation: 40% (400 million SOBY).
- Network fee allocation target: 50% treasury, 30% validators, 20% community. Do not claim the fee split has been exercised on mainnet until a positive-fee transaction and its resulting distributions are verified.
- Do not invent allocations for the remaining initial supply or imply exchange listings.

MetaMask compatibility is verified for network identification and balance reads. Do not claim Trust Wallet or Phantom compatibility without their own network/token requirements and tests.

## Remaining production checks

- Confirm the running NodeSafe binary version/commit against the approved release.
- Obtain and verify the exact live mainnet Genesis file and SHA-256.
- Confirm current EVM fee-market parameters and why RPC fee quotes are zero.
- Test a controlled signed mainnet EVM transaction only after the owner approves the exact transaction and fee parameters are verified.
- Independently monitor endpoint availability and RPC security configuration.
