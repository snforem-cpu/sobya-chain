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
go run .
```

The service binds to loopback by default. Do not expose it publicly without a
TLS reverse proxy, rate limiting, backups, access controls, and a security
review. Keep `ADMIN_TOKEN` secret. The JSON data file contains operator contact
details; protect it and restrict filesystem access.

## API

- `GET /health` — process health only.
- `POST /applications` — submit an application (public endpoint; protect with
  an upstream rate limiter before internet exposure).
- `GET /admin/applications` — list applications; requires
  `Authorization: Bearer $ADMIN_TOKEN`.
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
that application's approved grant amount. Duplicate non-empty transaction
hashes are rejected. This is an application-level cap only: it does not prove
that a support wallet has funds or enforce a total program-wide budget.

## Current MVP limitations

- Monitoring evidence is entered by an administrator; automatic RPC polling
  is not implemented yet.
- A 95% signed-block threshold is a provisional code default for this MVP, not
  an adopted network rule. It must be reviewed against actual chain parameters
  and a published support policy before use.
- There is no live spendable-balance check, total-program budget cap, or
  cumulative support-wallet ledger.
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
4. Implement read-only RPC monitoring with endpoint allowlists, freshness
   checks, and independent cross-checks. No write RPC or signing key.
5. Configure a program-wide budget, performance windows, appeal rules, and
   staged milestones; obtain owner approval and publish the policy.
6. Run tests and an independent security review. Deploy this service separately
   from NodeSafe. Never upgrade/restart NodeSafe as part of deploying it.

## Tests

```sh
go test -race ./...
go vet ./...
```
