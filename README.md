![SOBYA official logo](assets/logo/sobya-coin-128.png)

# SOBYA Chain

SOBYA is an in-development Cosmos SDK / CometBFT blockchain with a partially integrated Cosmos EVM environment. The active development branch is `feature/tokenomics-fee-split`. This repository is public; the project is not yet a live public network.

## Native token and agreed tokenomics

- Display symbol: `SOBY`
- Base denomination: `asobya`
- Precision: 18 decimal places (`1 SOBY = 10^18 asobya`)
- Intended maximum native supply: 1,000,000,000 SOBY (`10^27 asobya`)
- Agreed allocation: Founder 40%, Community 20%, Validators 15%, Development 10%, Liquidity 10%, Treasury 3%, Emergency 2%.
- Transaction fees: 50% Treasury, 30% Validators, 20% Community.
- Automatic inflation is disabled under the current token rules.

See [tokenomics and launch rules](sobya/TOKENOMICS.md). Production wallet destinations and validator gentxs must be validated in the final genesis ceremony; development balances are not production allocations.

## Development capabilities and evidence

The development branch contains Cosmos SDK transaction processing, native 18-decimal denomination configuration, fee-routing and validator-reserve logic, local multi-validator workflows, and Cosmos EVM integration work. These are distinct capabilities and must be judged against completed CI runs on the exact commit.

A passing build or local CI network does not establish public consensus, a production genesis, continuous hosting, or full wallet compatibility. See [EVM integration status](docs/COSMOS_EVM_INTEGRATION.md) and the current [GitHub Actions runs](https://github.com/snforem-cpu/sobya-chain/actions).

## Stage three — independent operator preparation

The stage-three preparation pack is now documented:
1. [Independent validator/operator onboarding kit](docs/STAGE_THREE_OPERATOR_KIT.md)
2. [Genesis ceremony and launch-bundle procedure](docs/GENESIS_CEREMONY.md)
3. [Versioned binary release process](docs/RELEASE_PROCESS.md)
4. [Arabic/English recruitment announcements and application template](docs/ANNOUNCEMENTS.md)
5. [P2P/RPC security and external connectivity checks](docs/testnet/NETWORK_CONNECTIVITY_STAGE_TWO.md)

The project can invite expressions of interest from independent operators now. Actual node startup must wait for a tested versioned release, approved CometBFT and EVM chain IDs, final genesis and SHA-256, peer list, and coordinated launch time. The first public network should be a testnet rehearsal; mainnet requires a separate approval and launch ceremony.

## Current operational status

- No public peer address, public RPC endpoint, production genesis hash, or independently operated validator is currently confirmed in this repository.
- The EVM chain ID `777777` is development/CI only and must not be reused for a public network.
- GitHub Actions runners are temporary CI machines, not validator hosting.
- The repository includes a tagged Linux amd64 prerelease workflow. It has not published a release merely by being added; a reviewed version tag and successful workflow are required.
- No mainnet launch, token sale, investment return, or exchange-listing claim is authorized.

## Security

Never commit or share mnemonics, private keys, keyring directories, `priv_validator_key.json`, or `node_key.json`. Each operator generates and retains their own keys. Testnet tokens have no monetary value, and no validator income or infrastructure reimbursement is promised.
