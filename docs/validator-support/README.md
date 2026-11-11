# SOBYA Validator Support Program (Off-chain, isolated)

## Safety boundary

This program is an off-chain administrative service. It MUST NOT be imported by
`sobya/app`, registered as an SDK module, added to consensus hooks, or change
genesis, app wiring, staking parameters, validator-reserve accounting, fee
routing, or the running NodeSafe node.

Development and deployment are separate from the live chain. No deployment,
wallet signing, token transfer, validator restart, or software upgrade is
performed by this repository change.

## Purpose

Provide conditional, staged onboarding grants to independent validator
operators. The program helps eligible operators obtain the funds needed to
meet the chain's actual self-delegation requirement without charging an
application fee.

## Important distinction

The existing on-chain `validator_reserve` is a consensus-controlled rewards
mechanism. Its balance and permissions must not be treated as a liquid
onboarding budget. This program must use a separately verified, spendable
support wallet/budget. The existence and balance of such a budget are not
assumed by this design.

## Grant lifecycle

1. Application: collect operator address, validator operator address (when
   available), consensus public key, node/P2P endpoint, software version,
   proposed commission, and operational contact. Never request seed phrases,
   private keys, or validator signing keys.
2. Eligibility review: verify chain ID, binary release, node synchronization,
   unique operator identity, current staking parameters, actual minimum
   self-delegation, and available support budget.
3. Approval: human approval records the amount, vesting/milestones, monitoring
   window, and policy version. No automatic approval or transfer.
4. Staged disbursement: pay small, explicitly approved tranches from a
   separate support wallet. The operator controls its own wallet and signs
   its own create-validator/delegation transactions.
5. Monitoring: read-only observations from public RPC (or independently
   operated trusted endpoints) track bonded status, signed-block ratio,
   uptime/availability, jailed status, and evidence timestamps.
6. Completion or suspension: release later tranches only when configured
   milestones are met. Stop future tranches when conditions fail and allow a
   human appeal/review.

## Irreversibility and enforcement

On-chain transfers are generally irreversible. Do not describe an already
transferred grant as automatically recoverable, and do not implement a
privileged clawback. Conditionality is enforced primarily by staged payments:
unreleased tranches remain in the support wallet. Any voluntary repayment is
a separate transaction initiated by the recipient.

## Security controls

- Separate support wallet from founder, treasury, emergency, liquidity, and
  validator-reserve accounts.
- Multisignature or equivalent two-person approval for every payout.
- Hard per-validator and total-program budget caps.
- Idempotency key per application and payout; duplicate prevention.
- Immutable audit log of decisions, evidence, transactions, and policy version.
- Read-only RPC credentials; no validator private-key access.
- Fail closed when RPC data is stale, inconsistent, or unavailable.
- Never automatically jail, unbond, slash, or alter a validator.
- No automated transaction signing in the initial release.

## Initial policy defaults (not yet approved for production)

All numeric thresholds and grant amounts remain unset until the live chain is
read and verified. In particular, do not assume a 1 SOBY minimum or any
particular self-delegation amount. Eligibility thresholds must be configurable
and published before applications open.

## Acceptance criteria

- Unit tests cover duplicate applications, budget exhaustion, stale RPC data,
  missed performance thresholds, and payout idempotency.
- Integration tests use a local disposable testnet only.
- A security review confirms that the service cannot write to chain state,
  change consensus behavior, or access validator signing keys.
- CI proves the new directory is independent of the chain runtime.
- No production deployment or transfer occurs without explicit owner approval.


## Fast path for new validators

Use the [live validator onboarding guide](ONBOARDING.md) and the public
[validator application form](../../issues/new?template=validator-application.yml).
Applications are free. Technical admission and any conditional support grant
are separate decisions; no grant is promised before the spendable support
budget is verified.
