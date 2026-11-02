# SOBYA (SOBY) token rules — EVM compatibility development

## Native denomination and precision

- Native base denomination: `asobya`.
- Display denomination: `SOBY`.
- Precision: 18 decimal places.
- Conversion: `1 SOBY = 1,000,000,000,000,000,000 asobya`.
- Staking power reduction is set to `10^18` base units per SOBY.

The 18-decimal choice is intended to align the native gas asset with Ethereum/EVM wallet conventions. It does not, by itself, mean Cosmos EVM has been integrated or that EVM wallets can connect yet.

## Maximum native supply

- Maximum: `1,000,000,000 SOBY`.
- In base units: `1,000,000,000,000,000,000,000,000,000 asobya` (`10^27`).
- The application represents this cap with the Cosmos SDK arbitrary-precision integer type, not `int64`.
- Genesis initialization rejects a native allocation above this maximum.
- Automatic inflation is disabled in the current application. The mint module remains in the required block lifecycle order, but genesis initialization forces inflation parameters, current inflation, and annual provisions to zero.

The cap applies to native `asobya`. IBC voucher denominations are separate assets and are not native SOBY issuance.

## Development allocations (not a launch distribution)

The Ignite development configuration contains test balances, scaled to preserve their previous SOBY-denominated values:

- Alice: `20,000 SOBY`.
- Bob: `10,000 SOBY`.
- Validator test bonds: `100`, `200`, and `100 SOBY`.

These are development-only test values. They are not an approved public launch allocation, treasury allocation, or final genesis distribution.

## Agreed economic decisions not yet implemented

- Founder allocation: 40% of the maximum supply (400 million SOBY), with the
  full founder allocation available at network launch.
- Transaction-fee distribution target: 50% treasury, 30% validators, and 20%
  community.
- Validator allocation is intended to vest gradually and remain conditional on
  actual validator participation; a validator that stops participating must
  not continue earning future unvested rewards.

These are design decisions, not active on-chain rules yet. The current source
does not implement the custom 50/30/20 fee routing or participation-based
validator rewards. Treasury, liquidity, development, emergency, and community
wallets and the remaining genesis allocations still need their final amounts,
addresses, and release rules.

## Rules not yet finalized

No production values have been finalized in source for:

- transaction fee amount, gas pricing, and exact implementation of the agreed
  fee split;
- validator commission, reward eligibility, participation measurement, and
  slashing/claim logic;
- staking minimums, unbonding period, and validator eligibility;
- treasury, community pool, ecosystem, team, or public distribution;
- governance voting thresholds and upgrade authority;
- public Cosmos chain ID, EVM chain ID, genesis time, validator set, or launch date;
- public RPC, REST, gRPC, Ethereum JSON-RPC, P2P and explorer endpoints.

## EVM integration status

Cosmos EVM `v0.6.0` is the candidate compatibility baseline because its Cosmos SDK and CometBFT versions match this source tree. The EVM application is not yet integrated into SOBYA. Integration still requires wiring EVM, ERC-20, fee-market, ante handling, JSON-RPC, precompiles, module lifecycle, and a single canonical representation of the native asset. Dependency compatibility alone is not an integration.

Do not treat the development genesis or test validator balances as production parameters. Do not use this network for real funds until EVM integration (if adopted), fixed-supply invariants, launch configuration, security review, independent multi-node testing, and public-network operations are complete.
