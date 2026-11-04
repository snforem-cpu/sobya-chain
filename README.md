![SOBYA official logo](assets/logo/sobya-coin-128.png)

# SOBYA Chain

SOBYA is an in-development Cosmos SDK and CometBFT blockchain project with a partially integrated Cosmos EVM execution environment. The repository is private and development work is being carried out on `feature/tokenomics-fee-split`.

## Native token

- Display symbol: `SOBY`
- Base denomination: `asobya`
- Precision: 18 decimal places (`1 SOBY = 10^18 asobya`)
- Intended maximum native supply: 1,000,000,000 SOBY
- Automatic mint inflation is disabled in the current genesis normalization.

See [tokenomics and launch rules](sobya/TOKENOMICS.md).

## Verified development capabilities

The current development branch contains:
- Native Cosmos SDK transaction processing and 18-decimal denomination configuration.
- Runtime transaction-fee routing: 70% combined to the configured shared management wallet and 30% left for the standard validator/delegator distribution path.
- A local integration workflow that has exercised actual Cosmos and EVM fee-paying transactions and checked fee accounting.
- EVM JSON-RPC, signed-transaction, and Solidity contract test workflows.
- A two-validator localnet smoke-test workflow.

These are development/CI checks. They do not establish a public network, independently operated validators, production genesis, or mainnet readiness. Check the workflow runs and the exact commit SHA before treating any test as current.

## Current launch blockers

Before a public testnet can be announced, SOBYA still needs:
1. A finalized testnet chain ID, EVM chain ID, genesis, validator onboarding and allocation procedure.
2. A reviewed implementation for the 150 million SOBY validator reserve, including release schedule, eligibility, voting-power allocation, and unclaimed/slashed reward handling.
3. Multi-validator fee/reward tests and tests of fixed-supply invariants across all issuance paths.
4. A tested operator package, reproducible binaries, genesis checksum, peer discovery, public RPC policy, faucet, monitoring, backups, and recovery procedures.
5. At least two independently operated hosts completing public P2P consensus and cross-node transactions.
6. Security review and a coordinated testnet rehearsal.

The current EVM chain ID `777777` is a development/CI value, not an approved public network identifier.

## Repository safety

- Do not use this development chain for real funds.
- Never commit private validator keys, node keys, mnemonics, or wallet secrets.
- GitHub Actions runners are temporary CI machines, not persistent blockchain infrastructure.
- No mainnet launch, token sale, or exchange-listing claim is authorized by the current development status.

## Independent validator onboarding

The operator recruitment pack is available at [docs/VALIDATOR_RECRUITMENT.md](docs/VALIDATOR_RECRUITMENT.md). It explains the independent-host model, operator safety rules, required launch bundle, readiness sequence, application template, and a draft recruitment notice. It is preparation material only; it does not mean a public testnet is live.
