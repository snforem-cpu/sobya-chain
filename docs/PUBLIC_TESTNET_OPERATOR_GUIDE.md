# Legacy public-testnet guide — archived

This historical filename is retained so older repository links do not break. **It is not an operator guide for the current network. SOBYA Mainnet is live and this repository's public testnet launch-preparation process is obsolete.**

Use these current resources instead:

- [Main repository overview and live network endpoints](../README.md)
- [Live validator onboarding](validator-support/ONBOARDING.md)
- [Network identity and EVM configuration](../sobya/readme.md)
- [Release process](RELEASE_PROCESS.md)
- [P2P/RPC connectivity and security reference](testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

Production network identifiers are CometBFT `sobya-1` and EVM `357812033857`. Do not use the historical testnet examples or local CI identifiers `777777` / `777778` to connect to Mainnet. A validator joining the running network must synchronize to the existing chain and use the supported live-chain validator-creation transaction; it must not create a new genesis or submit a genesis gentx.

All operators retain their own private keys and signing files. Never send mnemonics, keyrings, validator private keys, or node keys to the coordinator.
