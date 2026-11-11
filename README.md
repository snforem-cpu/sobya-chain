![SOBYA official logo](assets/logo/sobya-coin-128.png)

# SOBYA Chain

SOBYA is a Cosmos SDK / CometBFT blockchain project. The configured public chain identifier in the operator launch materials is sobya-1. Repository status, an accepted Genesis file, and a scheduled startup are not by themselves proof that a public network is currently producing blocks; live operation must be confirmed from independent, read-only network evidence.

## Native token and agreed tokenomics

- Display symbol: SOBY
- Base denomination: asobya
- Precision: 18 decimal places (1 SOBY = 10^18 asobya)
- Intended maximum native supply: 1,000,000,000 SOBY (10^27 asobya)
- Agreed allocation: Founder 40%, Community 20%, Validators 15%, Development 10%, Liquidity 10%, Treasury 3%, Emergency 2%.
- Transaction fees: 50% Treasury, 30% Validators, 20% Community.
- Automatic inflation is disabled under the current token rules.

See [tokenomics and launch rules](sobya/TOKENOMICS.md). Production wallet destinations and validator allocations must be validated against the approved Genesis package; development balances are not production allocations.

## Development capabilities and evidence

The repository contains Cosmos SDK transaction-processing code, native 18-decimal denomination configuration, fee-routing and validator-reserve logic, local multi-validator workflows, and Cosmos EVM integration work. These capabilities must be judged against completed CI runs on the exact commit.

A passing build or local CI network does not establish public consensus, continuous hosting, or full wallet compatibility. See [EVM integration status](docs/COSMOS_EVM_INTEGRATION.md) and the current [GitHub Actions runs](https://github.com/snforem-cpu/sobya-chain/actions).

## Validator participation

Independent operators may submit a no-fee expression of interest through the [public GitHub validator application form](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml). Intake is manual: submitting an issue does not call the separate Go support service, approve a grant, or create a validator.

Read the [validator onboarding guide](docs/validator-support/ONBOARDING.md) before applying. Do not generate a new genesis gentx to join a network that has already started. A joining operator must synchronize to the verified live chain and create its validator using the supported live-chain transaction flow only after the team confirms the current binary, chain state, staking parameters, minimum self-delegation, and fees.

## Current operational status (documentation review: 2026-11-11)

- Chain ID in the operator launch materials: sobya-1.
- NodeSafe reported acceptance of the single-validator launch Genesis with SHA-256 35207c189ee5548cb376cb4d5d9dbe4aa0509b3daf85b057e8e59db1c4b0314a, scheduled for 2026-11-10T16:00:00Z. This is an operator-reported launch artifact, not independent proof of current block production.
- NodeSafe previously supplied P2P endpoint 188.68.36.11:36656. Its current reachability and the current peer set must be checked before distributing connection instructions.
- No public RPC endpoint is currently published in this repository. NodeSafe's reported RPC address was loopback-only and is not usable by external applicants.
- Until an independently reachable read-only RPC endpoint and a recent block-height/chain-ID check are published, this repository does not claim that continuous public consensus has been independently verified. Do not send applicants transaction commands, self-delegation amounts, or fee figures based only on old configuration or Genesis files.
- The earlier two-validator Genesis draft is not the final launch artifact identified above. Do not use its validator list or hash for joining instructions.
- The EVM chain ID 777777 is development/CI only and must not be reused for a public network.
- GitHub Actions runners are temporary CI machines, not validator hosting.
- No mainnet investment, token sale, return, or exchange-listing claim is authorized by this repository.

## Validator support service status

The Go service under ops/validator-support is an isolated experimental administrative MVP. It is not deployed, is not connected to the GitHub issue form, does not query a live RPC, and cannot sign or broadcast transactions. GitHub Issues are the only currently documented application intake path. Do not treat an example/configured budget cap as evidence of spendable funds.

## Security

Never commit or share mnemonics, private keys, keyring directories, priv_validator_key.json, or node_key.json. Each operator generates and retains their own keys. Applicants must never send secrets through GitHub Issues.
