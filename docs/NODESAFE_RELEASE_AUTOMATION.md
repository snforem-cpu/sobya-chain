# SOBYA — NodeSafe release automation handoff

## Goal

After the one-time NodeSafe integration, a **published stable GitHub Release** becomes the single deployment trigger. Developers work in feature branches and pull requests; passing CI alone never changes the live network. Publishing an approved stable release invokes NodeSafe with the immutable tag, source commit, Linux amd64 binary asset URL, and SHA-256 checksum. NodeSafe upgrades the existing node in place and reports the result.

This repository-side preparation does not grant access to NodeSafe and cannot deploy until NodeSafe implements the receiver contract and the repository secrets/environment below are configured.

## Current candidate / initial adoption

- Repository: https://github.com/snforem-cpu/sobya-chain
- Initial candidate branch: `release/v0.1.1-rc.1`
- Candidate commit: `2b0c9b6bbb19a879c1cc3882fba568dc57b2507d`
- Candidate validation evidence: 11 successful GitHub check runs on the tested source commit `dd36e991f6d87f5a887f3e4affa610143c1b04cd`; the release branch points at the squash merge commit whose source tree was verified identical.
- The candidate is not yet a stable GitHub Release and is not automatically deployed by the stable-release workflow. NodeSafe must perform the initial RC adoption explicitly, after reviewing the binary/source and the existing chain state. Once that one-time integration is complete, future stable releases use the automatic path.

## Required GitHub configuration (one time)

Create a GitHub Actions environment named `sobya-production`. Protect it with required reviewers / deployment approval if supported by the repository plan.

Add these **environment secrets** (never commit their values):

- `NODESAFE_DEPLOY_URL`: HTTPS endpoint supplied by NodeSafe for the SOBYA production deployment receiver.
- `NODESAFE_DEPLOY_TOKEN`: dedicated, revocable bearer token accepted only by that receiver. It must not be a node key, wallet key, mnemonic, SSH private key, or general hosting credential.

The workflow deliberately fails closed if either secret is absent. Do not put secrets in workflow files, release notes, issue comments, or chat.

## NodeSafe receiver contract

NodeSafe must provide an HTTPS endpoint that accepts:

`POST NODESAFE_DEPLOY_URL`

Headers:
- `Authorization: Bearer <NODESAFE_DEPLOY_TOKEN>`
- `Content-Type: application/json`

JSON body:
- `schema_version`: `1`
- `repository`: `snforem-cpu/sobya-chain`
- `release_tag`: immutable Git tag, e.g. `v0.1.2`
- `source_commit`: full 40-character Git commit SHA resolved from that tag
- `chain_id`: `357812033857`
- `evm_chain_id_hex`: `0x534f425941`
- `base_denom`: `asobya`
- `decimals`: `18`
- `asset_url`: exact GitHub release asset URL for `sobyad-<tag>-linux-amd64.tar.gz`
- `checksum_url`: exact GitHub release asset URL for `SHA256SUMS`

The receiver must authenticate the request, validate repository/tag/commit/chain parameters, download the assets over HTTPS, verify SHA-256 before installation, and reject unknown or replayed release tags unless explicitly authorized.

### Mandatory safe-upgrade behavior

NodeSafe must:
1. Confirm the currently running chain ID and node identity before changing anything.
2. Take and verify a consistent backup/snapshot of the existing node data and configuration, including the current binary/version and rollback plan.
3. Preserve the existing chain database, validator identity, private-validator state, node key, genesis, persistent volumes, and all account balances. **Never run `init`, replace genesis, reset the database, or create a new chain as part of an application upgrade.**
4. Confirm the new binary is compatible with the current app/state version. If a coordinated Cosmos SDK store migration or chain halt/upgrade height is required, stop and request an explicit upgrade plan; do not perform an ordinary binary swap.
5. Install atomically, restart the existing service, and keep the old binary available for rollback.
6. Verify CometBFT is producing blocks and that the EVM JSON-RPC is healthy on the existing chain.
7. Return success only after post-deployment checks pass. If checks fail, restore the previous binary/configuration and report failure; do not silently reset or reinitialize chain data.

### Synchronous response contract

The endpoint must return HTTP 200 only after the rollout and health checks are complete, with JSON similar to:

```json
{
  "status": "success",
  "deployment_id": "nodesafe-generated-id",
  "release_tag": "v0.1.2",
  "deployed_commit": "<full 40-character SHA>",
  "chain_id": 357812033857,
  "height": "12345",
  "checks": {
    "cometbft_rpc": true,
    "block_production": true,
    "evm_chain_id": true,
    "eth_gas_price": true,\n    "eth_max_priority_fee": true,
    "eth_estimate_gas": true,
    "eth_fee_history": true,
    "existing_data_preserved": true,
    "rollback_available": true
  }
}
```

Return a non-2xx response or `status` other than `success` for any incomplete/failed deployment. The workflow has a 30-minute timeout. NodeSafe should reject or safely queue requests that cannot complete within that window and provide an operator-visible deployment status.

The exact endpoint path and response schema are an integration contract proposed by SOBYA; NodeSafe must confirm/adapt it before the secret is configured. Do not assume NodeSafe already exposes this API.

## Post-upgrade verification required

Use the existing endpoints, not a fresh chain:
- CometBFT: `https://sobya-rpc.nodesafe-app.xyz/status`
- EVM JSON-RPC: `https://sobya-evm-rpc.nodesafe-app.xyz`
- Chain ID decimal: `357812033857`
- EVM `eth_chainId`: `0x534f425941`

At minimum check `eth_chainId`, `eth_gasPrice`, `eth_maxPriorityFeePerGas`, `eth_estimateGas`, and `eth_feeHistory`; verify block production and that the pre-upgrade chain height/data continue forward. A real value transfer should be tested only after the upgrade is confirmed, preferably by NodeSafe using a controlled test account. Never use founder/shared-wallet funds as an unverified deployment probe.

## Ongoing developer workflow

1. Implement changes on a feature branch.
2. Open a PR into the approved release/development branch; review changes and pass the relevant unit, localnet, multi-validator, EVM transaction/contract, fee-routing, and configuration checks on the exact candidate commit.
3. Merge only after checks pass.
4. Create a new immutable version tag and publish a **stable** GitHub Release only after compatibility/upgrade review and approval.
5. GitHub Actions invokes NodeSafe automatically. The workflow fails if deployment is not confirmed.
6. Review the deployment result and verify the live RPCs before announcing the release.

A failed CI run, prerelease, ordinary branch push, or draft release never updates production. No source change can safely update the live chain instantaneously without a running deployment agent at the hosting provider.
