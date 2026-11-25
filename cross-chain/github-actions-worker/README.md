# SOBYA GitHub Actions settlement worker

The worker is intentionally fail-closed. It does not process deposits unless the
repository variable `CROSSCHAIN_AUTOMATION_ENABLED` is explicitly set to `true`.
It is not a real-time API: the schedule is every 15 minutes and GitHub may delay it.

## What it does

- Verifies Ethereum (chain ID 1), SOBYA EVM (chain ID 357812033857), canonical
  Ethereum USDT, configured escrow operator/treasury, and configured vault relayer.
- Scans only finalized Ethereum blocks, in bounded ranges, from the configured
  escrow deployment block.
- Validates each on-chain order against its event, a fixed configured SOBY/USDT
  rate, and hard maximum order limits.
- Pays native SOBY from the inventory vault once, waits for destination
  confirmations, marks the Ethereum order fulfilled, then releases USDT to the
  immutable treasury address.
- Saves the scan cursor in the separate `sobya-crosschain-state` branch.
  A failed batch does not advance the cursor; vault replay protection makes
  already-submitted payouts detectable on retry.

## Required GitHub repository secrets

- `ETHEREUM_RPC_URL`
- `ETHEREUM_OPERATOR_PRIVATE_KEY` — dedicated key matching the escrow operator
- `SOBYA_EVM_RPC_URL`
- `SOBYA_RELAYER_PRIVATE_KEY` — dedicated, limited-inventory relayer key

## Required GitHub repository variables

- `CROSSCHAIN_AUTOMATION_ENABLED` — leave unset/false until deployment and audit
- `ETHEREUM_ESCROW_ADDRESS`
- `ETHEREUM_DEPLOYMENT_BLOCK`
- `ETHEREUM_CONFIRMATIONS` (recommended 12 or more)
- `SOBYA_PAYOUT_VAULT_ADDRESS`
- `SOBYA_TREASURY_ADDRESS` (must equal the escrow's immutable treasury)
- `SOBYA_CONFIRMATIONS`
- `SOBY_PER_USDT` — fixed reviewed rate, expressed as SOBY per 1 USDT
- `MAX_USDT_MICRO` — maximum USDT amount in six-decimal base units per order
- `MAX_SOBY_WEI` — maximum SOBY payout in 18-decimal base units per order
- `SCAN_BLOCK_SPAN` — 1 to 5000 (default 1500)
- `MIN_DEADLINE_REMAINING_SECONDS` — at least 600; use a substantial safety buffer

Do not use the owner's primary wallet keys. Never put secrets in repository files,
PR comments, browser code, or GitHub variables. Keep customer deposits disabled
until independent contract review, mainnet deployment verification, and a small
end-to-end test have passed. The operator/relayer model remains trusted and is
not a trustless bridge.
