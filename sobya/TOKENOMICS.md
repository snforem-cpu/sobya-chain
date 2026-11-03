# SOBYA (SOBY) tokenomics and launch rules

## Native denomination and precision

- Native base denomination: `asobya`.
- Display denomination: `SOBY`.
- Precision: **18 decimal places**.
- Conversion: `1 SOBY = 1,000,000,000,000,000,000 asobya`.
- Staking power reduction: `10^18` base units per SOBY.
- The native token logo is included in the repository at `assets/logo/sobya-coin-128.png`.

## Maximum native supply

- Maximum: **1,000,000,000 SOBY**.
- In base units: `1,000,000,000,000,000,000,000,000,000 asobya` (`10^27`).
- The application represents this cap with the Cosmos SDK arbitrary-precision integer type, not `int64`.
- Genesis initialization rejects a native allocation above this maximum.
- Automatic inflation is disabled in the current application. The mint module remains in the required block lifecycle order, but genesis initialization forces inflation parameters, current inflation, and annual provisions to zero.
- The cap applies to native `asobya`. IBC voucher denominations are separate assets and are not native SOBY issuance.

## Agreed initial supply allocation

The agreed distribution of the full 1 billion SOBY maximum supply is:

| Allocation | Share | Amount |
|---|---:|---:|
| Founder | 40% | 400,000,000 SOBY |
| Community | 20% | 200,000,000 SOBY |
| Validators | 15% | 150,000,000 SOBY |
| Development | 10% | 100,000,000 SOBY |
| Liquidity | 10% | 100,000,000 SOBY |
| Treasury | 3% | 30,000,000 SOBY |
| Emergency reserve | 2% | 20,000,000 SOBY |
| **Total** | **100%** | **1,000,000,000 SOBY** |

The founder allocation is available at network launch. The validator allocation is intended to vest/release gradually and remain conditional on actual validator participation; a validator that stops participating must not continue earning future unvested rewards.

The founder is responsible for the treasury, liquidity, emergency-reserve, and development wallets. These allocations are distinct from the founder's personal 40% allocation. The actual launch wallet addresses, genesis account entries, and any detailed release schedules must be populated in the production genesis package; they must not be replaced with guessed addresses or invented vesting terms.

## Agreed transaction-fee distribution

The target routing of network transaction fees is:

- **50%** to the founder-controlled treasury wallet.
- **30%** to eligible validators.
- **20%** to the community allocation/pool.

This split is an approved design requirement. It is **not yet implemented as custom on-chain fee-routing logic** in the current source. The implementation must account for actual collected fees, deterministic accounting, validator eligibility/participation, and transparent community accounting; do not treat the standard Cosmos distribution module as proof that this exact split is active.

## Development allocations and test data

The Ignite development configuration contains test balances and validator bonds. These are disposable development values, not the agreed production launch allocation. A production genesis must use the allocation table above and must validate that the total native supply equals no more than the 1 billion SOBY cap, with no accidental duplicate allocations.

## EVM integration status

The working branch contains partial Cosmos EVM `v0.6.0` integration: EVM, ERC-20 and fee-market keepers/modules, EVM-aware ante handling, unified EVM/Cosmos mempool and proposal handlers, and EVM server command/configuration paths. The development EVM chain ID currently defaults to `777777`; it is a **development value only**, not an approved production network identifier.

The integration is not yet considered complete or production-ready. Required verification and remaining work include:
- starting the node with Ethereum JSON-RPC and WebSocket endpoints enabled;
- validating `eth_chainId`, block queries, balances, signed EIP-155 transactions, transaction receipts, and Solidity contract deployment/calls/state/logs;
- verifying ERC-20 conversion and native-asset mapping end to end;
- testing the wired Cosmos EVM static precompiles, ERC-20 IBC middleware, and IBC contract callbacks;
- implementing and testing the agreed 50/30/20 fee routing;
- implementing and testing validator reward release based on participation;
- testing genesis allocation, wallet control, and fixed-supply invariants.

## Launch and operational policy

- No presale.
- No promises of exchange listing.
- The project is to be fully prepared and tested before seeking independent validators through X (formerly Twitter) and Telegram.
- GitHub Actions runners are temporary CI environments; they are not permanent validators or production hosting.
- A public network requires independent validator operators, persistent node infrastructure, public RPC/REST/gRPC/EVM JSON-RPC endpoints, monitoring, backups, an upgrade process, and a security review.

Do not use this network for real funds until the production genesis, independent multi-node operation, EVM behavior, tokenomics enforcement, and security/operational readiness have all been verified.
