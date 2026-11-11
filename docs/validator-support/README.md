# SOBYA Validator Support Program (Off-chain, isolated)

## Current status and intake

The public application route is GitHub Issues and is handled manually by the SOBYA team:
[Submit a validator application](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml).

The GitHub issue form is **not integrated** with the Go service described below. An issue does not create an API record, trigger an automated review, approve a grant, or transfer funds. Follow-up takes place in the public issue unless the applicant and team arrange a safer private channel for non-public contact details. Never post secrets or private credentials in an issue.

The Go service is an experimental, standalone administrative MVP only. It is not hosted or production-ready. Do not advertise it as an application portal or expose it to the public internet.

## Safety boundary

This program is an off-chain administrative service. It MUST NOT be imported by
sobya/app, registered as an SDK module, added to consensus hooks, or change
genesis, app wiring, staking parameters, validator-reserve accounting, fee
routing, or the running NodeSafe node.

No deployment, wallet signing, token transfer, validator restart, or software
upgrade is performed by this repository change.

## Purpose

The intended program may consider conditional, staged onboarding grants to
independent validator operators. There is no promise of support, and no grant
may be approved until a separate spendable support budget and the published
policy are verified. Applicants pay no application fee.

## Important distinction

The existing on-chain validator_reserve is a consensus-controlled rewards
mechanism. Its balance and permissions must not be treated as a liquid
onboarding budget. Any support must come from a separately verified,
spendable support wallet/budget. Its existence and balance are not assumed.

## Grant lifecycle

1. Manual application review using public operator details only.
2. Verify chain ID, exact binary release, synchronization, unique operator
   identity, current staking parameters, actual minimum self-delegation, and
   spendable support budget from trusted sources.
3. Human approval records amount, milestones, monitoring window, and policy
   version. No automatic approval or transfer.
4. If approved, authorized humans prepare and sign staged transfers using a
   separately approved wallet procedure. The recipient controls its own keys.
5. Monitoring is manual in this MVP. Do not claim automatic RPC monitoring.
6. Stop future tranches when conditions fail; provide a human appeal/review.

## Irreversibility and enforcement

On-chain transfers are generally irreversible. Do not describe an already
transferred grant as automatically recoverable or implement a privileged
clawback. Conditionality is enforced by staged payments: unreleased tranches
remain in the support wallet.

## Security controls

- Separate support wallet from founder, treasury, emergency, liquidity, and
  validator-reserve accounts.
- Two-person approval for every payout.
- Hard per-validator and total-program budget caps.
- Idempotency and auditable records for every decision and payout.
- Read-only RPC access only after trusted endpoints are established.
- Never automatically jail, unbond, slash, or alter a validator.
- No automated transaction signing.

## Initial policy defaults (not approved for production)

All thresholds and grant amounts remain unset. Do not assume a 1 SOBY minimum
or any particular self-delegation amount. Publish eligibility thresholds only
after verification against the running chain and owner approval.

## Acceptance criteria before production

- Unit and integration tests cover application validation, duplicate records,
  budget exhaustion, stale evidence, and payout idempotency.
- Integration tests use a disposable local testnet only.
- Independent security review confirms no chain-state writes or access to
  validator signing keys.
- Production storage, backups, TLS, rate limiting, privacy controls, audit-log
  integrity, and multi-person payout approval are implemented and reviewed.
- No production deployment or transfer occurs without explicit owner approval.
