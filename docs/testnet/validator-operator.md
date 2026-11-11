# SOBYA Validator Operator Guide

This page is retained as a stable entry point. SOBYA mainnet is live on `sobya-1`. The complete current operator instructions and live preflight status are maintained in:

- [Validator onboarding and live preflight status](../validator-support/ONBOARDING.md)
- [Genesis ceremony](../GENESIS_CEREMONY.md)
- [Release verification process](../RELEASE_PROCESS.md)
- [P2P/RPC connectivity and security guide](NETWORK_CONNECTIVITY_STAGE_TWO.md)

**Important:** public CometBFT RPC, Cosmos REST, and EVM JSON-RPC endpoints have passed external read-only checks. The previously supplied P2P endpoint `188.68.36.11:36656` timed out from an external runner, and CometBFT reported zero connected peers. Do not create a production gentx or broadcast `create-validator` until a reachable P2P/seed endpoint or verified State Sync method, supported binary/checksum, live Genesis checksum, and current staking/fee parameters are confirmed.

Generate and retain all account, node, and private-validator keys locally. Never send mnemonic phrases, keyrings, private keys, `priv_validator_key.json`, or `node_key.json` to the coordinator. Operators must sign their own transactions.

Validator distributions follow the protocol reserve and signing-eligibility rules; no fiat return, market price, liquidity, or infrastructure reimbursement is promised.
