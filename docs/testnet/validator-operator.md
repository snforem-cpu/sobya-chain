# SOBYA Validator Operator Guide

This page is retained as a stable entry point. SOBYA mainnet is live on `sobya-1`. The complete current operator instructions and live preflight status are maintained in:

- [Validator onboarding and live preflight status](../validator-support/ONBOARDING.md)
- [Genesis ceremony](../GENESIS_CEREMONY.md)
- [Release verification process](../RELEASE_PROCESS.md)
- [P2P/RPC connectivity and security guide](NETWORK_CONNECTIVITY_STAGE_TWO.md)

**Important:** public CometBFT RPC, Cosmos REST, and EVM JSON-RPC endpoints have passed external read-only checks. NodeSafe's P2P TCP port `188.68.36.11:26656` is externally reachable and the Node ID was verified through RPC. A second independent node has not yet completed a P2P handshake and block sync. Do not create a production gentx or broadcast `create-validator` until the exact live Genesis/checksum, running binary, and current staking/self-delegation/fee parameters are confirmed.

Generate and retain all account, node, and private-validator keys locally. Never send mnemonic phrases, keyrings, private keys, `priv_validator_key.json`, or `node_key.json` to the coordinator. Operators must sign their own transactions.

Validator distributions follow the protocol reserve and signing-eligibility rules; no fiat return, market price, liquidity, or infrastructure reimbursement is promised.
