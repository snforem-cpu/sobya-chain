# SOBYA Validator Support Service (MVP)

This is a standalone off-chain administrative API. It lives under `ops/`, not
under `sobya/app`. It does not compile into the chain binary, register an SDK
module, connect to a write RPC, sign transactions, transfer funds, or control
validator processes.

## Run locally

Requires Go 1.23 or newer.

```sh
cd ops/validator-support
export ADMIN_TOKEN="$(openssl rand -hex 32)"
export LISTEN_ADDR="127.0.0.1:8097"
export DATA_FILE="./data/validator-support.json"
# Required: total approved support budget in verified base-denomination units
# Optional: leave unset until a separate spendable support budget is verified.
# Without a valid value, grant approvals and the budget endpoint stay disabled.
unset SUPPORT_BUDGET_BASE_UNITS
go run .
```

The service binds to loopback by default. It is not connected to GitHub Issues and is not an applicant portal. Do not expose it publicly without a
TLS reverse proxy, rate limiting, backups, access controls, and a security
review. Keep `ADMIN_TOKEN` secret. The JSON data file contains operator contact
details; protect it and restrict filesystem access.

## API

- `GET /health` — process health only.
- `POST /applications` — submit an application (public endpoint; protect with
  an upstream rate limiter before internet exposure).
- `GET /admin/applications` — list applications; requires
  `Authorization: Bearer $ADMIN_TOKEN`.
- `GET /admin/budget` — show configured, approved, and remaining program
  budget in base-denomination units; requires the admin token.
- `POST /admin/applications/{id}/approve` — record a human-approved grant
  amount and notes.
- `POST /admin/applications/{id}/evidence` — append a manually reviewed,
  timestamped performance snapshot.
- `POST /admin/applications/{id}/tranches` — record a planned, paid, or
  withheld tranche. A paid tranche requires a transaction hash; the service
  only records it and never broadcasts it.
- `POST /admin/applications/{id}/complete` — mark an active operator as
  having completed the support period.

Admin authentication uses an exact bearer token comparison. JSON requests reject
unknown fields, trailing JSON values, and bodies larger than 1 MiB. All payout
actions are records only: an authorized human must independently verify the
budget and prepare/sign the transfer using the project's approved wallet
procedure.

## Grant accounting

Amounts must be positive integer base-denomination units (for SOBYA, use the
verified live-chain base denom; do not assume display-unit amounts). Each
application's planned, paid, and withheld tranches are summed and cannot exceed
that application's approved grant amount. The sum of all approved grants is also
checked against the required `SUPPORT_BUDGET_BASE_UNITS` ceiling. The service
reserves the full approved amount in its accounting, even before tranches are
paid. This is an administrative cap only: it does not prove that a support
wallet has funds or verify its on-chain balance.

## Current MVP limitations

- Monitoring evidence is entered by an administrator; automatic RPC polling
  is not implemented yet.
- A 95% signed-block threshold is a provisional code default for this MVP, not
  an adopted network rule. It must be reviewed against actual chain parameters
  and a published support policy before use.
- There is no live spendable-balance check or cumulative support-wallet ledger.
  The configured program-wide ceiling is not a balance oracle.
- There is no automatic repayment/clawback. Conditionality is implemented by
  withholding future tranches, not reversing irreversible transfers.
- JSON-file storage is suitable only for isolated development/testing, not a
  production multi-user deployment.

## Mandatory safety gates before production

1. Confirm a separate, spendable support budget on the live chain. Do not use
   the consensus-controlled validator rewards reserve as if it were liquid.
2. Verify actual chain ID, denomination, current minimum self-delegation, and
   validator eligibility rules against the running release and live chain.
3. Replace local JSON storage with a reviewed database and backups; add TLS,
   rate limiting, audit-log integrity, and multi-person payout approval.
4. Implement read-only RPC monitoring only after trusted RPC endpoints, chain ID,
   validator consensus-address mapping, and monitoring windows are verified.
   Applicant-supplied endpoints must never be fetched blindly. No write RPC or
   signing key.
5. Configure a program-wide budget, performance windows, appeal rules, and
   staged milestones; obtain owner approval and publish the policy.
6. Run tests and an independent security review. Deploy this service separately
   from NodeSafe. Never upgrade/restart NodeSafe as part of deploying it.

## Tests

```sh
go test -race ./...
go vet ./...
```


## Fast validator intake

For the manual public application form and the live-network joining checklist, see
[`docs/validator-support/ONBOARDING.md`](../../docs/validator-support/ONBOARDING.md).
The GitHub issue form collects public operator information only and does not call this API; it is not a
grant approval and must never be used to collect secrets. Do not publish this
service as an internet-facing application portal until production hosting,
TLS, rate limiting, privacy controls, and a reviewed data store are in place.
