# Enzonic deployment

Use the Git branch `enzonic-safe-start` after reviewing its pull request.

## Enzonic settings

- Runtime: keep the existing Python container for the initial idle-start test.
- Main file: `cross-chain/custodial/enzonic_start.py`
- Repository root `requirements.txt` includes the canonical custodial dependencies from `cross-chain/custodial/requirements.txt`.
- Keep all wallet, RPC, and passphrase environment variables unset for the initial idle-start test.
- Do not add private keys, seed phrases, keystore contents, or passphrases to GitHub.

## First start behavior

The launcher creates `cross-chain/custodial/config.json` from `config.example.json` only when the local config is absent. It verifies that the feature gate and all four network gates are false before creating the file. The generated file is local to the server and is not committed back to GitHub.

With the default config, the payout worker creates its local SQLite state files and stays alive in disabled/idle mode. It does not load wallet adapters, read payout orders, sign transactions, or broadcast transactions.

## Before enabling any network

Do not change `featureEnabled` or any network `enabled` flag until RPC connectivity, keystore loading, fee balances, chain finality, inventory checks, limits, and a small controlled test have been independently verified. The initial Enzonic start is only an idle process test, not a live exchange launch.
