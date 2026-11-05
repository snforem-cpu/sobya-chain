# SOBYA production Genesis preparation

**Status: PREPARATION ONLY — not a production Genesis, not frozen, and not a launch authorization.**

This preparation record was checked against the `main` source snapshot at commit
`5f9bb2e27816ebcbe57b573e536c1dc3bf414b85` (the latest commit at the time of review).

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

## Owner-approved production network parameters

The project owner explicitly approved the following production candidates on
2026-11-05. The final launch bundle must repeat these values and all operators
must use them consistently.

- **CometBFT chain ID:** `sobya-1` (owner-approved).
- **Production EVM chain ID:** `357812033857` (`0x534f425941`, ASCII bytes for
  `SOBYA`; owner-approved). This value is within JavaScript's exact-integer
  range and the uint64 range accepted by SOBYA. The corresponding entry was
  not found at `ethereum-lists/chains/eip155/357812033857.json` when checked
  on 2026-11-05. Registry absence is not a reservation and cannot prove that
  no private chain uses it; recheck the public registry immediately before
  publishing the launch bundle. The repository's `777777` and `777778`
  values remain development/CI-only.
- **Minimum Cosmos gas price:** `1000000000asobya` per gas
  (1e-9 SOBY/gas; owner-approved). Every validator and RPC node must use this
  same `minimum-gas-prices` value; the configuration auditor enforces it.
  This local admission-price setting is distinct from the EVM fee-market
  base fee, which is separately initialized and validated at genesis.
- **Not yet fixed:** genesis UTC time, release tag, validator self-bond amount,
  peer list, and coordinated launch time.

CometBFT chain ID and EVM chain ID are separate identifiers. The approved
production pair is CometBFT `sobya-1` and EVM `357812033857`. This approval
does not itself create or authorize a production genesis, release, or network
launch.

**Owner-provided MetaMask destinations recovered from the earlier project discussion:**
- Founder wallet (400M SOBY): `0xd316993423Fc6268038F4EE3EA7C0C5038513C18` → SOBYA account encoding `sobya16vtfjdprl33xsqu0fm375lqv2qu9z0qc0097pq`.
- Shared wallet for Community, Treasury, Development, Liquidity, and Emergency (450M SOBY combined): `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f` → SOBYA account encoding `sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3`.

Both Bech32 strings were checksum-decoded and verified to contain exactly 20 bytes, with byte-for-byte values matching the two owner-supplied EVM hex addresses. This matches the exact Cosmos EVM v0.6.0 `NewEvmCodec` behavior used by SOBYA: it accepts EVM hex or Bech32, requires the configured `sobya` HRP for Bech32, and applies the SDK account-address length check. This verifies address format and conversion only; it does not prove control of either wallet's private key. The shared wallet does not merge the five tokenomics categories: keep their separate amounts in the off-chain allocation ledger even though the on-chain bank genesis will contain one aggregated balance for that address.

The production allocation bootstrap also writes canonical `SOBY`/`asobya` bank metadata, fixes the EVM and extended EVM denoms to `asobya`, enables only the supported Cosmos EVM v0.6.0 static precompiles, sets mint inflation and annual provisions to zero, and sets distribution community tax to zero. The validator reconciliation script refuses to proceed if any of these canonical settings are missing or changed.

The `validator_reserve` address is an app-owned module account configured in the application's module-account permissions. It is intentionally not fabricated as a normal entry in the initial `auth.accounts` list: SOBYA's `InitChainer` creates the module account after auth/bank genesis, while the bootstrap script funds its deterministic bank address. The production preflight exercises this exact sequence with the real binary.

## Allocation ledger — destinations recorded; final sign-off pending

All amounts below are exact base units. Both owner-supplied destination addresses and their SOBYA Bech32 encodings are recorded and their codec format has been checked. Final production sign-off still requires the owner to verify the addresses in their own wallet and approve the exact destination-to-allocation mapping. No development/test address may be substituted.

| Allocation | SOBY | Base units (`asobya`) | Destination |
|---|---:|---:|---|
| Founder | 400,000,000 | 400000000000000000000000000 | EVM: `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`; SOBYA bech32: `sobya16vtfjdprl33xsqu0fm375lqv2qu9z0qc0097pq` |
| Community | 200,000,000 | 200000000000000000000000000 | Shared MetaMask EVM: `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`; SOBYA bech32: `sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3` |
| Validator reserve | 150,000,000 | 150000000000000000000000000 | `sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr` |
| Development | 100,000,000 | 100000000000000000000000000 | Shared MetaMask EVM: `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`; SOBYA bech32: `sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3` |
| Liquidity | 100,000,000 | 100000000000000000000000000 | Shared MetaMask EVM: `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`; SOBYA bech32: `sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3` |
| Treasury | 30,000,000 | 30000000000000000000000000 | Shared MetaMask EVM: `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`; SOBYA bech32: `sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3` |
| Emergency | 20,000,000 | 20000000000000000000000000 | Shared MetaMask EVM: `0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f`; SOBYA bech32: `sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3` |
| **Total** | **1,000,000,000** | **1000000000000000000000000000** | Must reconcile exactly |

For the actual `bank.balances` section, represent the shared address as one account balance of 450,000,000 SOBY (450000000000000000000000000 `asobya`), not five duplicate address entries. Keep the five category amounts separate in the signed allocation report: Community 200M, Development 100M, Liquidity 100M, Treasury 30M, Emergency 20M. The founder address receives 400M SOBY and the validator-reserve module account receives 150M SOBY. The EVM codec accepts either the 20-byte hex address or its valid `sobya` Bech32 form; use the canonical Bech32 form in Cosmos bank genesis and verify the owner-controlled wallets before signing off.

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

- Final owner sign-off that the two supplied wallet addresses are controlled by the owner and that the allocation mapping above is correct (the address encoding itself has been checked against the application codec).
- Confirmed production CometBFT chain ID and registry-checked EVM chain ID.
- Tested release-specific genesis/gentx commands and release binary.
- Validator set, signed gentxs, public P2P topology, and launch time.
- Reconciled final genesis, independent review, and SHA-256 sign-off.

Until these gates pass, this repository contains preparation material only.
It does not contain an approved production `genesis.json`, a live network, or
a guarantee that a validator can start a production chain today.
