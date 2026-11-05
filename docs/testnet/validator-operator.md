# SOBYA Validator Operator Guide

This page is retained as a stable entry point. The complete current operator instructions are maintained in:

- [Independent operator onboarding kit](../STAGE_THREE_OPERATOR_KIT.md)
- [Genesis ceremony and launch bundle](../GENESIS_CEREMONY.md)
- [Release verification process](../RELEASE_PROCESS.md)
- [Recruitment announcements and application template](../ANNOUNCEMENTS.md)
- [P2P/RPC connectivity and security guide](NETWORK_CONNECTIVITY_STAGE_TWO.md)

**Important:** the public testnet is not live. Do not use a proposed/example chain ID, development EVM ID `777777`, draft genesis, or guessed peer address. Wait for the official versioned launch bundle and verify its binary and genesis SHA-256 checksums.

Generate and retain all account, node, and private-validator keys locally. Never send mnemonic phrases, keyrings, private keys, `priv_validator_key.json`, or `node_key.json` to the coordinator. Operators share only public information and the signed gentx when the official genesis ceremony requests it.

Testnet tokens have no monetary value. No financial return or infrastructure reimbursement is promised.
