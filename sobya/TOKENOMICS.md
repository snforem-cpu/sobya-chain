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

The founder is responsible for the treasury, liquidity, emergency-reserve, and development wallets. These allocations are distinct from the founder's personal 40% allocation. The founder's public EVM address and the shared management address for the other five allocations have been supplied by the founder, but are not yet encoded into production genesis. The shared address is an administrative choice; accounting must continue to track each allocation separately. No production genesis should be generated until the addresses have been converted/validated against SOBYA's account codec and the allocation entries have been reviewed.

The validator reserve should be held by a protocol-controlled account, not by the founder's personal wallet. Validator wallet addresses are not needed before validators join: the future on-chain registration/reward mechanism must accept eligible validator operators dynamically without a code change for each new validator.

## Agreed transaction-fee distribution

The target routing of network transaction fees is:

- **50%** to the founder-controlled treasury wallet.
- **30%** to eligible validators.
- **20%** to the community allocation/pool.

The fee split is connected to the block lifecycle on this development branch:

- A deterministic pre-block hook runs the configured module pre-blockers, then reads the actual `fee_collector` balance before the distribution module begins.
- **70% combined (50% treasury + 20% community)** is transferred to the shared management wallet `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`. Because both allocations use the same address, the chain emits the combined transfer; the founder must keep the treasury and community ledgers separate off-chain.
- **30%** remains in `fee_collector` for the standard distribution module, preserving validator commission/delegator reward accounting.
- Genesis normalization sets the distribution community tax to **0%**, preventing the SDK's default 2% tax from reducing the intended validator share.
- Rounding remainder is assigned to treasury; the split is denomination-aware and conserves every collected coin. A transfer failure aborts block finalization rather than silently dropping funds.

If the distribution module sees no bonded voting power for a block, the Cosmos SDK's standard zero-power fallback sends the remaining validator-designated amount to its protocol community pool. This is not an individual validator payment and must be considered when planning validator onboarding.

The code and unit tests establish the routing logic on this development branch; CI and local multi-node/EVM runs must pass on the resulting commit before this behavior is treated as verified. This does not mean the production genesis, validator reserve vesting, or mainnet launch is complete.

## Development allocations and test data

The Ignite development configuration contains test balances and validator bonds. These are disposable development values, not the agreed production launch allocation. A production genesis must use the allocation table above and must validate that the total native supply equals the 1 billion SOBY launch allocation, with no accidental duplicate allocations or unassigned remainder.

## EVM integration status

The working branch contains partial Cosmos EVM `v0.6.0` integration: EVM, ERC-20 and fee-market keepers/modules, EVM-aware ante handling, unified EVM/Cosmos mempool and proposal handlers, and EVM server command/configuration paths. The development EVM chain ID currently defaults to `777777`; it is a **development value only**, not an approved production network identifier.

The integration is not yet considered complete or production-ready. Required verification and remaining work include:
- starting the node with Ethereum JSON-RPC and WebSocket endpoints enabled;
- validating `eth_chainId`, block queries, balances, signed EIP-155 transactions, transaction receipts, and Solidity contract deployment/calls/state/logs;
- verifying ERC-20 conversion and native-asset mapping end to end;
- testing the wired Cosmos EVM static precompiles, ERC-20 IBC middleware, and IBC contract callbacks;
- implementing and testing the agreed 50/30/20 fee routing at runtime;
- implementing and testing validator reward release based on participation;
- testing genesis allocation, wallet control, and fixed-supply invariants.

## Launch and operational policy

- No presale.
- No promises of exchange listing.
- The project is to be fully prepared and tested before seeking independent validators through X (formerly Twitter) and Telegram.
- GitHub Actions runners are temporary CI environments; they are not permanent validators or production hosting.
- A public network requires independent validator operators, persistent node infrastructure, public RPC/REST/gRPC/EVM JSON-RPC endpoints, monitoring, backups, an upgrade process, and a security review.

Do not use this network for real funds until the production genesis, independent multi-node operation, EVM behavior, tokenomics enforcement, and security/operational readiness have all been verified.


## Validator reserve on-chain accounting

The feature branch adds a dedicated persistent multistore key (sobya_validator_reserve) and a blocked module account (validator_reserve). Commit accounting is performed in the pre-block lifecycle using the actual DecidedLastCommit.Votes supplied by CometBFT. The previous block's timestamp assigns its commit to the correct monthly period. Repeated execution of an already-recorded height is ignored, while unexpected height gaps or backwards block time fail closed.

The monthly share denominator includes the accumulated voting power of all validators expected during that period. Eligibility is applied independently at 95% or higher. An ineligible validator's pro-rata share is not redistributed within that period. Unpaid scheduled amounts remain in the reserve and roll forward into the cumulative budget for subsequent period closes; the cumulative budget is reduced by all prior payouts and remains bounded by the 150,000,000 SOBY lifetime cap and the actual reserve account balance. The 150,000,000 SOBY lifetime cap is tracked in persistent state in addition to the actual reserve account balance.

Production genesis must place 150,000,000 SOBY (150000000000000000000000000 asobya) in the validator_reserve module account as part of the already-agreed 1 billion SOBY allocation. Do not create new supply to fund it. The account is derived by the Cosmos SDK as `authtypes.NewModuleAddress("validator_reserve")`; with SOBYA's `sobya` prefix its address is `sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr`. Add its 150,000,000 SOBY balance to the `bank.balances` section of the production genesis, not as a user-controlled auth account:

```json
{
  "address": "sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr",
  "coins": [
    {
      "denom": "asobya",
      "amount": "150000000000000000000000000"
    }
  ]
}
```

This balance must be deducted from the already-agreed validator allocation when constructing the full 1 billion SOBY genesis; it is not an additional issuance. The module account is blocked from ordinary bank sends and has no mint permission. If it is not funded, the release mechanism remains dormant rather than minting or borrowing funds.

Reserve payouts enter x/distribution and are allocated to each eligible validator's distribution record. The normal commission split applies, so operator commission and delegator rewards follow standard Cosmos distribution behavior. A validator that exits after earning a period's entitlement can still receive that completed period's accrued reward if its staking record remains available; a removed validator's unpaid share stays in reserve.

This code is on the feature branch and still requires successful repository CI and integration verification before it is considered Testnet-ready. It does not itself constitute a production genesis ceremony or public network launch.
