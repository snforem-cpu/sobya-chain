# SOBYA Genesis Ceremony and Launch Bundle

**Status: procedure defined; production genesis is not created or approved.** The final validator set, operator public addresses, network IDs, genesis time, and gentx files are not yet available. Never invent these values.

## 1. Freeze the release inputs

The coordinator publishes a ceremony proposal and freezes:
1. Exact SOBYA source commit and release version.
2. CometBFT chain ID (unique string).
3. Proposed EVM chain ID `357812033857` (`0x534f425941`, ASCII-derived from SOBYA), subject to owner sign-off and a final registry check. Never use development/CI values `777777` or `777778`.
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

The proposed production identifier pair is CometBFT `sobya-1` and EVM `357812033857` (`0x534f425941`). These are candidates only until the owner approves them and the final launch manifest freezes them. The EVM candidate was not listed in ethereum-lists/chains on 2026-11-05; registry absence does not reserve an ID or prove no private chain uses it. The owner-supplied founder and shared management EVM addresses and their `sobya` Bech32 encodings have been checksum-decoded and verified byte-for-byte: each Bech32 value contains exactly 20 bytes matching its corresponding EVM hex address. This matches the Cosmos EVM v0.6.0 address codec used by this application, which accepts EVM hex or `sobya` Bech32 and validates the decoded address length. This verifies address format and conversion, not private-key ownership. The owner must verify both addresses in their wallet and sign off on the destination mapping before production genesis. The shared address is one on-chain bank balance (450M SOBY) while the five allocation categories remain separate in the approved off-chain ledger. Never infer or copy an address from an old development genesis.

The genesis native supply must reconcile exactly to the approved total and must not exceed the application cap. Inflation/mint issuance remains disabled under the agreed token rules. Any discrepancy, duplicate balance, unexpected denom, or unaccounted remainder blocks approval.

### Initial fixed allocation — prepare this before validators arrive

After `sobyad init` has created the empty application genesis and its module accounts, add the two owner-controlled accounts with the exact canonical Bech32 destinations and amounts:

```bash
sobyad genesis add-genesis-account sobya16vtfjdprl33xsqu0fm375lqv2qu9z0qc0097pq 400000000000000000000000000asobya --home "$SOBYA_HOME"
sobyad genesis add-genesis-account sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3 450000000000000000000000000asobya --home "$SOBYA_HOME"
python3 scripts/initialize-production-genesis.py \
  --genesis "$SOBYA_HOME/config/genesis.json" \
  --output "$SOBYA_HOME/config/genesis.base.json"
```

The bootstrap script validates the two exact owner allocations and the pre-existing `validator_reserve` module account, adds 150M SOBY to that module account's bank balance without replacing its module-account permissions, recalculates bank supply, and requires exactly 1B SOBY total native supply. Use the output as the initial coordinator genesis. Its self-test runs in GitHub Actions. Do not use `add-genesis-account` to replace the reserve module account with a normal account.

### Initial validator self-bonds — deterministic reserve accounting

The validator self-bonds are funded **from inside** the 150,000,000 SOBY validator allocation. They must not be added on top of the reserve or counted twice. The repository now includes `scripts/prepare-validator-genesis.py` to reconcile this safely after operators provide public account addresses and the agreed self-bond amounts:

1. Initialize the coordinator genesis with the exact release binary and add the founder, shared management wallet, and 150M reserve allocation.
2. For each participating validator, add the operator's public account address with exactly the agreed self-bond amount using `sobyad genesis add-genesis-account <sobya-account-address> <amount>asobya`. This command creates the auth account and initial bank balance needed for the operator's gentx.
3. Create `validators.json` as a JSON array of objects with `address` and `self_bond_asobya` (integer string) fields. Use the exact same address and amount used in `add-genesis-account`.
4. Run `python scripts/prepare-validator-genesis.py --genesis <path-to-genesis.json> --validators validators.json --output <reconciled-genesis.json>`.
5. The script validates each `sobya` Bech32 address/checksum, requires the matching auth and bank accounts, deducts the self-bond total from the 150M reserve module balance, recalculates all bank supply denominations, and requires native supply to remain exactly 1B SOBY. It writes the app-owned `sobya_validator_reserve` genesis extension with `total_paid_asobya` equal to the initial self-bonds, so the 150M lifetime ceiling and 48-tranche schedule account for them.
6. Use the reconciled genesis as the coordinator genesis, then have each operator generate a gentx for exactly the funded self-bond amount. Collect and validate gentxs with the release binary. Any mismatch between the funded amount and the gentx must block the ceremony.

The script refuses duplicate execution, unknown/duplicate validator addresses, missing auth/bank accounts, an underfunded reserve, self-bonds above the 150M lifetime cap, or a post-reconciliation native supply other than exactly 1B SOBY. Its self-test is part of GitHub Actions. Never send private keys, mnemonics, keyrings, or validator signing files to the coordinator.

## 4. Build and validate deterministically

Using the exact release binary and documented version-specific command sequence:
1. Generate the agreed initial genesis.
2. Apply only reviewed allocation changes.
3. Collect the approved gentx files.
4. Run `sobyad genesis collect-gentxs` and `sobyad genesis validate-genesis` using the same release binary.
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
