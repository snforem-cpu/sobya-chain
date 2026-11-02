# SOBYA (SOBY) token rules — development specification

## Approved denomination

- Native base denomination: `usobya`.
- Display denomination: `SOBY`.
- Precision: 6 decimal places.
- Conversion: `1 SOBY = 1,000,000 usobya`.

## Maximum native supply

- Maximum: `1,000,000,000 SOBY`.
- In base units: `1,000,000,000,000,000 usobya`.
- Genesis initialization rejects an allocation above this maximum.
- The mint module remains in the required block lifecycle order, but genesis initialization sets its denomination to `usobya` and forces inflation minimum, maximum, rate change, current inflation, and annual provisions to zero. The current application therefore issues no automatic native-token inflation. Any future change to minting must be reviewed against the supply cap.

The cap applies to the native `usobya` denomination. IBC voucher denominations are separate assets and are not native SOBY issuance.

## Development allocations (not a launch distribution)

The Ignite development configuration currently creates:
- Alice: `20,000,000,000 usobya` (20,000 SOBY).
- Bob: `10,000,000,000 usobya` (10,000 SOBY).

These are test balances used to exercise accounts, transfers, fees, and validator setup. They are not an approved public launch allocation, treasury allocation, or final genesis distribution.

## Rules not yet finalized

No production values have been approved in source for:
- transaction fee schedule or fee split;
- validator commission and any validator reward policy;
- staking minimums, unbonding period, and validator eligibility;
- treasury, community pool, ecosystem, team, or public distribution;
- governance voting thresholds and upgrade authority;
- public chain ID, genesis time, validator set, or launch date.

Do not treat the development genesis or test validator balances as production parameters. Do not use this network for real funds until the launch configuration, security review, independent multi-node testing, and public-network operations are complete.
