# Enzonic deployment

Deploy from the Git branch `enzonic-swap-worker` (PR #50 has been merged into this branch).

## Required Enzonic settings

- Runtime: **Python 3.12**. This entry point is Python; a Go runtime/container cannot execute it.
- Main file: `cross-chain/custodial/enzonic_start.py`
- Install dependencies from the repository-root `requirements.txt`, which includes `cross-chain/custodial/requirements.txt`.
- Keep private keys, seed phrases, keystore contents, and passphrases out of GitHub and source files.

## What this process actually runs

This entry point starts the **custodial payout worker only**. It does not start the public exchange interface, quote/order API, or the network deposit watchers. A successful process start is not a live exchange launch.

For a first process check, leave all wallet, RPC, and passphrase environment variables unset. The launcher creates a local config from the disabled example and the worker remains idle with every payout gate disabled.

## Before enabling real payouts

Do not enable `featureEnabled` or any network flag until the full coordinator/API and deposit-watcher processes are deployed and supervised, the exact inventory addresses and chain IDs are verified, RPC endpoints respond correctly, encrypted keystores and passphrases are installed as environment/runtime secrets, fee balances and inventory are verified, and an end-to-end controlled test passes.

The example config is a template, not production configuration. In particular, `referenceLiquidityUsdtBaseUnits` and operational limits must be set from verified values before quote creation. Do not infer these values or enable live payouts with null limits.
