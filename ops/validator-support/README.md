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

Admin endpoints require the bearer token. All payout actions are records only:
an authorized human must independently verify the budget and prepare/sign the
transfer using the project's approved wallet procedure.

## Current MVP limitations

- Monitoring evidence is entered by an administrator; automatic RPC polling
  is not implemented yet.
- A 95% signed-block threshold is a provisional code default for the MVP, not
  an adopted network rule. It must be reviewed against actual chain parameters
  and a published support policy before use.
- Amounts are recorded as strings; no spendable balance, reserve, grant cap,
  or cumulative budget is inferred or enforced yet.
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
5. Configure grant caps, performance windows, appeal rules, and staged
   milestones; obtain owner approval and publish the policy.
6. Run tests and security review. Deploy this service separately from NodeSafe.
   Never upgrade/restart NodeSafe as part of deploying this service.

## Tests

```sh
go test -race ./...
go vet ./...
```
