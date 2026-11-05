# SOBYA production Genesis preparation

**Status: PREPARATION ONLY — not a production Genesis, not frozen, and not a launch authorization.**

This document is based on the canonical `main` source tree at merge commit
`7b7b14da898d63107e5425981389c2ba520be55b`.

## Verified protocol constants

| Field | Value | Evidence |
|---|---|---|
| Native base denomination | `asobya` | `sobya/app/genesis.go`, `sobya/config.yml`, `sobya/TOKENOMICS.md` |
| Display denomination | `SOBY` | `sobya/app/genesis.go` |
| Display precision | 18 decimals | `sobya/app/genesis.go` |
| Maximum native supply | 1,000,000,000 SOBY = 10^27 `asobya` | `sobya/app/genesis.go` |
| Founder allocation | 400,000,000 SOBY | approved tokenomics table |
| Community allocation | 200,000,000 SOBY | approved tokenomics table |
| Validator lifetime allocation | 150,000,000 SOBY | approved tokenomics table |
| Development allocation | 100,000,000 SOBY | approved tokenomics table |
| Liquidity allocation | 100,000,000 SOBY | approved tokenomics table |
| Treasury allocation | 30,000,000 SOBY | approved tokenomics table |
| Emergency allocation | 20,000,000 SOBY | approved tokenomics table |
| Validator reserve module account | `sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr` | derived in `sobya/TOKENOMICS.md` |
| Development EVM chain ID | `777777` | documented as development-only; forbidden for public launch |

The allocation rows sum to exactly 1,000,000,000 SOBY. The validator reserve
must be funded within the 150M validator allocation, never on top of the cap.
The application genesis normalizer disables inflation and validates the native
supply ceiling.

## Chain identifiers — not yet frozen

- **Proposed CometBFT chain ID:** `sobya-1`. This is a proposal for the production
  network identifier, not a value already embedded in an approved genesis.
  It must be checked against any previously published SOBYA network and then
  frozen before operators create gentxs.
- **Production EVM chain ID:** intentionally unset. The repository currently
  uses `777777` for development and its own network-config self-test uses
  `777778`; neither is approved for production. A production integer must be
  checked against the current EVM chain registry and wallet/network ecosystem
  before it is committed. Do not infer that an unlisted integer is reserved.
- **Genesis UTC time, release tag, minimum gas price, self-bond amount, peer
  list, and launch time:** unset until the release and validator ceremony are
  agreed.

CometBFT chain ID and EVM chain ID are separate values and must not be confused.

## Allocation ledger — addresses required

All amounts below are exact base units. Blank destination fields are deliberate
blocking inputs; no placeholder or old development address may be substituted.

| Allocation | SOBY | Base units (`asobya`) | Destination |
|---|---:|---:|---|
| Founder | 400,000,000 | 400000000000000000000000000 | **REQUIRED: owner-confirmed SOBYA account address** |
| Community | 200,000,000 | 200000000000000000000000000 | **REQUIRED: owner-confirmed destination / sub-ledger** |
| Validator reserve | 150,000,000 | 150000000000000000000000000 | `sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr` |
| Development | 100,000,000 | 100000000000000000000000000 | **REQUIRED: owner-confirmed destination** |
| Liquidity | 100,000,000 | 100000000000000000000000000 | **REQUIRED: owner-confirmed destination** |
| Treasury | 30,000,000 | 30000000000000000000000000 | **REQUIRED: owner-confirmed destination** |
| Emergency | 20,000,000 | 20000000000000000000000000 | **REQUIRED: owner-confirmed destination** |
| **Total** | **1,000,000,000** | **1000000000000000000000000000** | Must reconcile exactly |

The shared management wallet may be used for the five owner-managed categories
only if the owner explicitly confirms that exact public address and the genesis
allocation report preserves the categories as separate accounting entries.
The founder's EVM hex address must be converted/validated using the actual
SOBYA account codec; do not copy a hex address into a bech32 field blindly.

## What can be prepared before validators

1. Freeze and review denomination, precision, supply cap, allocation arithmetic,
   module-account funding, mint/inflation settings, and fee routing.
2. Agree the CometBFT and EVM chain IDs and the source release commit.
3. Validate all owner-controlled destination addresses and publish an allocation
   ledger with no missing or duplicate funds.
4. Build and test a deterministic genesis-generation/reconciliation procedure
   using the exact release binary.
5. Publish the operator instructions and recruit independent operators.

## What must wait for validator operators

1. Collect each operator's public account address, moniker, node ID, public P2P
   endpoint, and signed gentx. Never collect private keys, mnemonics, keyrings,
   or validator signing files.
2. Validate gentxs against the frozen source version, chain ID, denomination,
   and approved self-bond. Initial self-bonds must be counted inside the 150M
   validator allocation, not double-counted.
3. Collect and reconcile gentxs, run the release binary's genesis validation,
   and independently verify all module/user balances and total supply.
4. Publish the final genesis SHA-256 and launch manifest; each operator verifies
   the exact same hash before coordinated startup.

## Hard launch blockers

- Owner-confirmed public account destinations for the allocations above.
- Confirmed production CometBFT chain ID and registry-checked EVM chain ID.
- Tested release-specific genesis/gentx commands and release binary.
- Validator set, signed gentxs, public P2P topology, and launch time.
- Reconciled final genesis, independent review, and SHA-256 sign-off.

Until these gates pass, this repository contains preparation material only.
It does not contain an approved production `genesis.json`, a live network, or
a guarantee that a validator can start a production chain today.
