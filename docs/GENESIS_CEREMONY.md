# SOBYA Genesis Ceremony and Launch Bundle

**Status: procedure defined; production genesis is not created or approved.** The final validator set, operator public addresses, network IDs, genesis time, and gentx files are not yet available. Never invent these values.

## 1. Freeze the release inputs

The coordinator publishes a ceremony proposal and freezes:
1. Exact SOBYA source commit and release version.
2. CometBFT chain ID (unique string).
3. EVM chain ID (unique integer; never use development/CI value 777777).
4. Genesis UTC time and launch time.
5. Minimum gas price and tested validator self-bond.
6. Supported binary platforms and SHA-256 checksums.
7. The allocation ledger, account codec/address format, and public P2P peer list.

All operators acknowledge the same proposal before signing gentxs. Changes after freeze require a new ceremony version and fresh review.

## 2. Collect validator contributions safely

Each operator generates account, node, and private-validator keys locally. The operator submits only the public account address, moniker, node ID, reachable P2P endpoint, and signed gentx created with the exact coordinator-published command.

The coordinator must reject duplicate validator identities, malformed gentxs, unexpected chain IDs, wrong denominations, invalid self-bond amounts, and any submission that includes secrets. Never collect private-validator keys, node keys, mnemonics, keyrings, or wallet private keys.

## 3. Reconcile the 1 billion SOBY genesis allocation

Canonical native denomination: `asobya`; precision: 18 decimals; conversion: 1 SOBY = 10^18 asobya; maximum native supply: 1,000,000,000 SOBY = 10^27 asobya.

| Allocation | SOBY |
|---|---:|
| Founder | 400,000,000 |
| Community | 200,000,000 |
| Validators (lifetime cap) | 150,000,000 |
| Development | 100,000,000 |
| Liquidity | 100,000,000 |
| Treasury | 30,000,000 |
| Emergency reserve | 20,000,000 |
| **Total** | **1,000,000,000** |

The 150M validator allocation is the total lifetime validator budget. Initial validator self-bonds must be accounted **inside** this 150M lifetime allocation, not added on top. Before generating production genesis, the reserve implementation must be tested with the chosen initial self-bond method so the reserve account is funded only with the unallocated remainder and already-created validator stake is not counted or paid twice. Do not create individual validator balances in addition to the same self-bond gentx amounts.

The owner-supplied founder and shared management addresses, plus their `sobya` Bech32 encodings, have been checked against the Cosmos EVM v0.6.0 address codec used by this application: EVM hex addresses decode to 20 bytes, and Bech32 addresses must use the `sobya` HRP and pass SDK address-format validation. This verifies address format, not private-key ownership. The owner must verify both addresses in their wallet and sign off on the destination mapping before production genesis. The shared address is one on-chain bank balance (450M SOBY) while the five allocation categories remain separate in the approved off-chain ledger. Never infer or copy an address from an old development genesis.

The genesis native supply must reconcile exactly to the approved total and must not exceed the application cap. Inflation/mint issuance remains disabled under the agreed token rules. Any discrepancy, duplicate balance, unexpected denom, or unaccounted remainder blocks approval.

## 4. Build and validate deterministically

Using the exact release binary and documented version-specific command sequence:
1. Generate the agreed initial genesis.
2. Apply only reviewed allocation changes.
3. Collect the approved gentx files.
4. Run the binary's `collect-gentxs` and `validate-genesis` commands.
5. Run application genesis validation and supply-cap checks.
6. Run the repository's tokenomics/reserve tests against this exact source commit.
7. Parse and independently reconcile all native balances and module-account balances.
8. Have a second reviewer reproduce the result from the same inputs.

Do not rely on an untested command copied from an older SDK release. The exact gentx flags and genesis commands must be exercised against the tagged release before the ceremony is called final.

## 5. Publish one immutable launch bundle

The bundle must contain:
- Version/tag and full source commit SHA.
- Supported binary and SHA-256 checksum file.
- Final `genesis.json` and SHA-256.
- Final CometBFT and EVM chain IDs.
- Minimum gas price and self-bond amount.
- Approved peer/seed list and node role profiles.
- Genesis allocation summary and reserve accounting report.
- UTC launch time, support contact, incident procedure, and upgrade policy.
- Operator configuration audit command.

Every validator independently downloads the bundle, verifies the binary and genesis hashes, checks the IDs, and confirms readiness. Any mismatch stops launch.

## 6. Sign-off and launch gate

Require explicit sign-off from the coordinator and participating operators for:
- Exact source commit and release artifacts.
- Both chain IDs and genesis time.
- Validator set and gentx list.
- Allocation and supply reconciliation.
- Genesis SHA-256.
- P2P topology and launch schedule.
- RPC exposure/security policy.

Do not describe the chain as a live public testnet until independent hosts connect over public P2P, commit blocks on the same chain, and complete cross-node transactions. Mainnet requires a separate reviewed genesis, release, security review, and explicit launch decision. Testnet success does not automatically authorize mainnet.

## 7. Immutable evidence

Archive the signed-off manifest, genesis hash, binary hashes, source commit, test results, operator acknowledgements, and launch checklist in the public repository/release. Never archive operator secrets or private validator files.
