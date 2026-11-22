# Enzonic deployment

Deploy from the Git branch `enzonic-swap-worker` (PR #50 has been merged into this branch).

## Required Enzonic settings

- Runtime: **Python 3.12**. This entry point is Python; a Go runtime/container cannot execute it.
- Main file: `cross-chain/custodial/enzonic_start.py`
- Install dependencies from the repository-root `requirements.txt`, which includes `cross-chain/custodial/requirements.txt`.
- Keep private keys, seed phrases, keystore contents, and passphrases out of GitHub and source files.

## What this process actually runs

This entry point starts the **unified custodial runtime**: the durable order-bound deposit-proof queue is checked first, then the payout worker processes only orders already advanced to `deposit_final`. It still does not provide the public exchange interface or quote/order API. The API/order layer must submit each user's transaction hash/signature and exact log/instruction index to the deposit queue; the runtime never guesses orders from shared-wallet balance changes. A successful process start is not a live exchange launch.

For a first process check, leave all wallet, RPC, and passphrase environment variables unset. The launcher creates a local config from the disabled example. Deposit watching and payouts both remain disabled. To configure read-only deposit verification later, set top-level `depositWatchEnabled=true`, then enable only the required per-network `depositWatchEnabled` flags and provide their HTTPS RPC environment variables. This does not enable payout signing.

## Before enabling real payouts

Do not enable `featureEnabled` or any network flag until the full coordinator/API and deposit-watcher processes are deployed and supervised, the exact inventory addresses and chain IDs are verified, RPC endpoints respond correctly, encrypted keystores and passphrases are installed as environment/runtime secrets, fee balances and inventory are verified, and an end-to-end controlled test passes.

The example config is a template, not production configuration. The payout worker is invoked only after the deposit queue has been processed in each cycle; it can therefore see a newly finalized deposit in the same cycle. In particular, `referenceLiquidityUsdtBaseUnits` and operational limits must be set from verified values before quote creation. Do not infer these values or enable live payouts with null limits.
