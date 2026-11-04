# SOBYA Public Testnet Launch Preparation

## Current status

The application-side reserve distribution path has passed a two-validator end-to-end test on commit `ec8206d151b3877dbced9c6df7362ffe8259f350`. The test created real validator commission and self-delegator rewards, committed all four withdrawal transactions, and verified that the same reserve period was not released again in the next block.

The following CI checks also passed on the source-code commit `a0257136a0eb59d101e167cd24b6b10fde385539`:

- Working-source and archived-source validation, full Go tests, and node build
- 18-decimal localnet smoke test
- Transaction fee-routing integration
- Two-validator localnet
- EVM JSON-RPC smoke test

This is **not yet a public network**. The CI network is ephemeral and runs on one GitHub runner. It is not a 24/7 host and does not provide independent public validators or public RPC endpoints.

## Network identity to finalize before genesis

- CometBFT chain ID: reserve `sobya-testnet-1` for the public testnet ceremony.
- EVM chain ID: choose and freeze one unique integer for the public testnet. The current default `777777` is for development/CI only and must not be reused for the public testnet.
- Base denomination: `asobya`.
- Display denomination: `SOBY`.
- Display exponent: 18.
- Maximum supply: 1,000,000,000 SOBY.
- All validators must use the exact same CometBFT chain ID, EVM chain ID, genesis file, and application version.

Do not start validators until the CometBFT and EVM chain IDs have been frozen and the final genesis hash has been shared with every operator.

## Genesis allocation rules

The agreed allocation totals 1,000,000,000 SOBY:

| Allocation | Amount |
|---|---:|
| Founder | 400,000,000 SOBY |
| Shared wallet (community, treasury, development, liquidity, emergency) | 450,000,000 SOBY |
| Validator allocation and reserve | 150,000,000 SOBY |
| **Total** | **1,000,000,000 SOBY** |

Wallets supplied for the project:

- Founder EVM address: `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`
- Shared EVM address: `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`

The genesis ceremony must account for initial validator self-bonds **inside** the 150,000,000 SOBY validator allocation. The sum of genesis self-bonds is deducted from the reserve module account and recorded as already allocated in the reserve's genesis `total_paid_asobya`. Do not add validator self-bonds on top of the 1B supply cap.

The validator reserve schedule is 3,125,000 SOBY per month for 48 months, subject to the 95% signing eligibility rule and voting-power weighting. Unpaid amounts carry forward. Initial validator self-bonds count against the 150M lifetime validator allocation.

## Fee policy

The transaction fee policy remains:

- 50% Treasury
- 30% Validators
- 20% Community

Because Treasury and Community share the agreed wallet, 70% of collected fees is routed to that shared wallet. The remaining 30% remains in the Cosmos distribution path for validator/delegator reward accounting.

## Minimum public infrastructure

Before calling the network public, recruit independent operators and obtain their node information:

1. At least four independent validator operators are recommended. With four similarly weighted validators, the network can continue if one is offline; three equal validators generally require all three to reach the greater-than-two-thirds commit threshold.
2. At least one non-validator full node should provide public RPC access. A separate seed/peer node is recommended.
3. Operators must supply their public P2P address and node ID, and keep their own private-validator keys on their own machines.
4. All operators must be able to download the same approved binary or build the exact approved source commit.
5. Publish a stable public RPC/EVM endpoint only after TLS, firewall, rate limits, and endpoint health checks are configured.

Typical ports to plan for are P2P 26656, CometBFT RPC 26657, REST 1317, gRPC 9090, EVM JSON-RPC 8545, and EVM WebSocket 8546. Do not expose node administration or unsafe RPC methods to the public internet.

GitHub Actions runners are suitable for CI only. They must not be treated as persistent validator hosting.

## Genesis ceremony

The coordinator must:

1. Freeze the source commit, CometBFT chain ID, EVM chain ID, and genesis parameters.
2. Receive signed gentx files from each validator operator. Operators must never send private-validator keys, keyring files, seed phrases, or private keys.
3. Derive each validator account address from its gentx and add only the agreed initial self-bond amount to that account.
4. Add the founder and shared-wallet allocations, fund the reserve module account with the remainder of the validator allocation, and set the reserve genesis `total_paid_asobya` to the total initial self-bonds.
5. Run `sobyad collect-gentxs` and `sobyad validate-genesis`.
6. Verify the asobya genesis supply equals exactly 1,000,000,000 SOBY and does not exceed the application supply cap.
7. Compute SHA-256 for the final genesis file and distribute the exact same file and hash to every operator.
8. Have every operator independently verify the hash before starting.

No genesis file is final until all validator gentxs are collected and validated.

## Public launch gate

Do not announce a live public testnet until all of the following are true:

- [ ] At least four independent validator operators confirmed
- [ ] Final CometBFT and EVM chain IDs frozen
- [ ] Genesis allocations and validator self-bonds reconcile to exactly 1B SOBY
- [ ] Every operator confirms the same genesis SHA-256
- [ ] Validators peer and reach consensus from separate hosts
- [ ] Public RPC and EVM RPC answer health checks from outside the hosting network
- [ ] Transfers, staking, delegation, rewards, fee routing, EVM transactions, and validator downtime/recovery have been exercised
- [ ] Binary checksums and operator instructions published
- [ ] Monitoring, backups, and incident contacts assigned

Until these gates are met, describe the network as **testnet preparation**, not a live public testnet or mainnet.
