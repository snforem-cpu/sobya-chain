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

The founder allocation is available at network launch. The validator allocation is held in the protocol-controlled validator_reserve module account and is released over 48 monthly-anniversary periods in UTC, anchored to the first finalized block. Each period has a maximum tranche of 3,125,000 SOBY. The application records actual CometBFT commit votes for each validator, counts every validator listed in the prior commit as an expected block, and requires at least 95% signed commits for that period. A validator's share is weighted by its accumulated consensus voting power across the period, not merely its power at the final block. Ineligible validators receive nothing; their shares and integer-rounding dust remain in the reserve. Each payout is routed through the Cosmos distribution module, so validator commission and delegator portions follow standard distribution rules. The application enforces a lifetime release ceiling of 150,000,000 SOBY and never mints reserve rewards. Production genesis must fund the reserve account with the 150,000,000 SOBY validator allocation; an empty or underfunded reserve cannot pay the scheduled tranche.

The founder is responsible for the treasury, liquidity, emergency-reserve, and development wallets. These allocations are distinct from the founder's personal 40% allocation. The founder and shared management wallet destinations are part of the launched network's allocation record. The shared address is an administrative choice; accounting must continue to track each allocation separately. Current balances and any subsequent transfers must be read from the live chain rather than inferred from this design table.

The validator reserve is held by a protocol-controlled module account, separate from the founder's personal wallet. New validator operators join the existing live network through the supported staking transaction flow; the reserve/reward logic applies to eligible validators under the on-chain rules.

## Agreed transaction-fee distribution

The target routing of network transaction fees is:

- **50%** to the founder-controlled treasury wallet.
- **30%** to eligible validators.
- **20%** to the community allocation/pool.

The fee split is connected to the production application block lifecycle:

- A deterministic pre-block hook runs the configured module pre-blockers, then reads the actual `fee_collector` balance before the distribution module begins.
- **70% combined (50% treasury + 20% community)** is transferred to the shared management wallet `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`. Because both allocations use the same address, the chain emits the combined transfer; the founder must keep the treasury and community ledgers separate off-chain.
- **30%** remains in `fee_collector` for the standard distribution module, preserving validator commission/delegator reward accounting.
- Genesis normalization sets the distribution community tax to **0%**, preventing the SDK's default 2% tax from reducing the intended validator share.
- Rounding remainder is assigned to treasury; the split is denomination-aware and conserves every collected coin. A transfer failure aborts block finalization rather than silently dropping funds.

If the distribution module sees no bonded voting power for a block, the Cosmos SDK's standard zero-power fallback sends the remaining validator-designated amount to its protocol community pool. This is not an individual validator payment and must be considered when planning validator onboarding.

The fee-routing logic is part of the launched SOBYA application. CI and local integration tests remain regression coverage for source changes; their local chain IDs and temporary networks are not the production network.

## Development allocations and test data

The Ignite development configuration contains test balances and validator bonds. These are disposable development values, not the agreed production launch allocation. A production genesis must use the allocation table above and must validate that the total native supply equals the 1 billion SOBY launch allocation, with no accidental duplicate allocations or unassigned remainder.

## Production EVM network

SOBYA Mainnet is live with Cosmos EVM enabled. The production identifiers are CometBFT `sobya-1` and EVM `357812033857`. The public EVM JSON-RPC endpoint is `https://sobya-evm-rpc.nodesafe-dapp.xyz`; the CometBFT RPC and REST endpoints are documented in the repository root README.

The production application includes EVM execution, Ethereum JSON-RPC transaction handling, fee-market and ERC-20 integration. The local development/CI chain IDs `777777` and `777778` are test fixtures only and must never be used for Mainnet.

Optional ecosystem capabilities such as particular IBC routes, external bridges, third-party wallet registry entries, and separately deployed dApps have independent status. Their implementation or deployment gates do not mean the core SOBYA EVM network is incomplete.
