# SOBYA Cosmos EVM Integration

Status: **partially wired; EVM runtime acceptance tests are not yet passing because the EVM RPC/mempool server path is not integrated.** Do not treat this branch as a public EVM network or claim wallet compatibility yet.

## Confirmed on the current feature branch

The feature branch pins github.com/cosmos/evm v0.6.0 and has passed compile/build validation with the current Cosmos SDK / CometBFT dependency set.

The SOBYA application currently contains:

- EVM, FeeMarket, and ERC-20 store keys and keepers in app/evm.go.
- Manual registration of the EVM, FeeMarket, and ERC-20 application modules.
- EVM ante-handler installation through evmante.NewAnteHandler.
- Runtime module lifecycle entries for EVM, FeeMarket, and ERC-20 in app/app_config.go.
- A development EVM chain ID default of 777777; this is not a production network ID.
- Native coin metadata configured as SOBY / asobya with 18 decimals.

The 3 November 2026 GitHub Actions runs on commit 5734ecfc92987e5bc866a4a97ab4067de06bada5 passed:
- Feature source validation, tests, and binary builds.
- 18-decimal native localnet initialization and block production.
- Two-validator P2P synchronization, validator-set query, and a signed native SOBYA bank transfer with exact integer balance-delta verification.

These tests prove Cosmos-native chain functionality only. They do not prove Ethereum transaction execution, EVM JSON-RPC, contract deployment, or wallet connectivity.

## Remaining EVM runtime work

1. **Ethereum-compatible encoding and transaction configuration**
   - Review the account, validator, and consensus address codecs.
   - Register Ethereum transaction decoding/signing correctly without duplicate protobuf signer extractors.
   - Verify the native SOBYA denomination maps to the EVM gas coin without a second supply.

2. **EVM mempool and proposal path**
   - Integrate the Cosmos EVM experimental mempool and its CheckTx / PrepareProposal handlers.
   - Wire pending-transaction notifications and CometBFT event-bus lifecycle.
   - Verify Cosmos SDK transactions continue to work through the same mempool.

3. **Node server and RPC**
   - Use the Cosmos EVM server startup path rather than the standard SDK-only start command.
   - Add explicit JSON-RPC and WebSocket configuration, API namespace allow-list, timeouts, gas caps, and safe CORS defaults.
   - Verify eth_chainId, net_version, eth_blockNumber, eth_getBalance, and WebSocket subscriptions on a running local node.

4. **EVM execution tests**
   - Submit an EIP-155 signed native-value Ethereum transaction through JSON-RPC.
   - Verify sender/recipient balances and nonce changes.
   - Deploy a small Solidity contract, call it, and verify stored state and emitted logs.
   - Test ERC-20 representation/conversion against the one canonical native supply.
   - Test fee-market charging and ensure no mint path can exceed the 1-billion-SOBY cap.

5. **Precompiles and IBC**
   - Review and add only the required Cosmos EVM static precompiles.
   - Integrate and test ERC-20/IBC transfer middleware and callbacks only after the keeper/address-codec wiring is validated.

6. **Production readiness**
   - Select and collision-check a permanent EVM chain ID before public genesis.
   - Finalize fee policy, including the agreed 50/30/20 fee allocation through explicit custom distribution logic.
   - Review validator economics, genesis allocation, upgrade safety, RPC exposure, monitoring, backups, and permanent validator hosting.

## Token rules that must remain invariant

- Native token: SOBY; base denomination: asobya.
- Precision: 18 decimal places.
- Maximum supply: 1,000,000,000 SOBY = 10^27 asobya, enforced with arbitrary-precision integers.
- Founder allocation: 40% (400 million SOBY), as previously agreed.
- Network fee allocation: 50% treasury, 30% validators, 20% community. This is separate from initial token allocation and is not yet implemented.
- Do not invent allocations for the remaining initial supply. Do not add a presale or imply exchange listings.

## Wallet and network claims

MetaMask/Rabby compatibility can only be claimed after a persistent public EVM JSON-RPC endpoint, the chosen EVM chain ID, and signed transaction tests are available. Cosmos wallet support requires working Cosmos RPC/gRPC/REST and published chain metadata. Trust Wallet and Phantom must not be claimed compatible without their own network/token requirements and tests.

A GitHub Actions runner is temporary infrastructure. A successful two-validator CI test is not a continuously available public network.

## Dependency note

The compatibility workflow pins Sonic v1.15.5 together with its matching github.com/bytedance/sonic/loader v0.5.3 module. Dependency compatibility and compilation do not establish EVM runtime functionality.
