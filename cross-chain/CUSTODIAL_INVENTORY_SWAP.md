# SOBYA Custodial Inventory Swap

The selected model is custodial inventory: one inventory wallet per supported network, automatic finalized-deposit detection, and payout from project inventory. No per-order escrow contracts or solver marketplace are required.

## User flows

- USDT to SOBY: select Ethereum, TRON, or Solana; bind the submitted transaction hash/signature and token event index to the order; verify asset, amount, recipient, success, and finality; check SOBY inventory; pay the user on SOBYA.
- SOBY to USDT: deposit SOBY to the SOBYA inventory; after finality, pay USDT from the selected external-chain inventory wallet.

The platform is custodial. Users must be informed that assets are held by project-controlled wallets and payout depends on available inventory and operational controls.

## Automation and safety

1. Bind each order to the exact transaction hash/signature and event index.
2. Watch finalized transactions using project-operated node infrastructure.
3. Credit each source event once.
4. Lock quotes in integer base units, apply fees and limits, and verify payout inventory.
5. Sign and broadcast payouts using local encrypted key custody. Never expose private keys in browser, repository, API requests, or logs.
6. Reconcile balances and pause orders if watchers are stale, liquidity is low, or a payout is unresolved.

Order lifecycle: CREATED -> DEPOSIT_SEEN -> DEPOSIT_FINAL -> PAYOUT_SUBMITTED -> COMPLETE. No payout before finalized-deposit verification; retries must inspect the original payout to prevent duplicate payment.

## Demand-based SOBY reference pricing

- Initial reference rate: 0.005 USDT per SOBY, matching the current manual selling reference.
- Only net finalized executed swap volume changes price. Elapsed time alone never changes it; the time window only measures flow and rejects stale snapshots.
- Net USDT-to-SOBY buy flow raises price using a stronger coefficient. Net SOBY-to-USDT sell flow lowers it using a weaker coefficient.
- Exponential impact model: base price multiplied by exp(sensitivity multiplied by net flow divided by verified reference liquidity). Upward sensitivity defaults to 10000 bps; downward sensitivity defaults to 2500 bps.
- No configured price ceiling or floor. The model can calculate values above 100 or 1000 dollars if sufficient net executed demand supports them. This does not guarantee executable market value: real inventory and liquidity must support payouts at quoted prices.
- Reference liquidity is intentionally unset in the sample. It must be derived from verified, executable SOBY inventory valued at the 0.005 dollar reference rate; never guess it. Without it, quote calculation fails closed.
- Count only finalized, deduplicated completed swaps. Exclude pending deposits, quotes, cancelled orders, failed payouts, replayed events, and wash trading.

The pricing module is a calculation component, not a live oracle, quote endpoint, or production volume aggregator. A production adapter must build authenticated snapshots from finalized ledger events and connect the calculation to the quote API and DEX UI. Watchers, reconciliation, local signing, payout broadcasters, and end-to-end tests remain required. All networks stay disabled until completed and tested.

## Implementation status (2026-11-21)

- The SQLite order ledger and asymmetric demand-pricing calculation have unit tests.
- The new `custodial/inventory_deposit_watchers.py` module adds read-only direct-inventory deposit verifiers for all four selected networks:
  - Ethereum: ERC-20 Transfer log, exact token contract, sender, inventory wallet, amount, receipt success, canonical block hash, and finalized block height.
  - TRON: TRC-20 Transfer log from the Solidity Node, exact contract/sender/inventory/amount, successful receipt, and solidified block identity.
  - Solana: finalized SPL Token transfer instruction, exact signature and instruction index, sender authority, configured USDT mint, amount, and destination token-account mint/owner.
  - SOBYA: native EVM transfer, exact chain ID, sender, inventory recipient, amount, successful receipt, canonical block, and finalized height.
- `InventoryDepositRecorder` passes verified evidence into the existing SQLite ledger. The ledger's unique (network, transaction, event-index) constraint prevents replaying one chain event into multiple orders, and its exact asset/amount/recipient checks remain in force.
- Unit tests and a dedicated GitHub Actions workflow have been added for the new verifier module. Their CI result must pass before this work can be marked complete.
- The order-bound `InventoryDepositService` derives sender, asset, amount, and inventory recipient from the persisted order; callers supply only transaction ID/signature and transfer index. `InventoryDepositWorker` persists submitted proofs, retries temporary RPC/finality delays across restarts, and marks invalid proofs failed without crediting the order. The host must run `run_forever` or schedule `run_once`, and the DEX/API must submit the exact transaction proof.
- The example config now pins Tether's published USDT identities: Ethereum ERC-20 `0xdAC17F958D2ee523a2206206994597C13D831ec7`, TRON TRC-20 `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`, and Solana mint `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB`; each uses 6 decimals. Solana's legacy SPL Token program is configured explicitly. Source: https://tether.to/en/supported-protocols/.
- Production RPC endpoint configuration and live-chain integration tests remain release requirements.
- The example config intentionally leaves every network and the feature disabled. No user deposits should be accepted and no payouts should be promised until the API integration, watcher liveness/restart recovery, and all release gates pass.

## Supplied inventory wallet addresses

The operator supplied these public receiving addresses for the inventory configuration:

- Ethereum mainnet: `0xebdb899fFE84a89e1d576964b640491c135651AD`
- TRON mainnet: `TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx`
- Solana mainnet-beta: `BMH7LJjaKkQRZd9EL4UqUfsTYEC44ZZoWSEdL1XWaSnh`
- SOBYA mainnet: `0xebdb899fFE84a89e1d576964b640491c135651AD`

The Ethereum and SOBYA entries intentionally use the same EVM address, but are separate balances on separate chains. These public addresses are recorded in the example configuration only; all network flags remain disabled. The operator reports that the SOBYA wallet holds 1,000,000 SOBY; that balance has not yet been independently checked by this software. Do not treat a configured address as proof of custody or signing capability: the corresponding private keys must remain under the operator's secure local control and must never be committed to GitHub.


## Payout implementation status (2026-11-21)

The shared-inventory payout path now has a durable execution layer and network adapters:

- `payout_executor.py`: immutable order-bound payout intent; owner-only SQLite journal; signed transaction bytes are persisted before broadcast; uncertain outcomes retry by rebroadcasting the exact same signed bytes, never by signing a second transfer; ledger completion requires adapter-confirmed finality.
- `evm_inventory_payout.py`: local signing and native SOBY transfer on SOBYA, and fixed ERC-20 `transfer(address,uint256)` USDT transfer on Ethereum. It validates chain ID, signer/inventory address, fee estimate, exact receipt sender/recipient/amount, successful receipt, canonical block and finalized block.
- `tron_inventory_payout.py`: locally signed TRC-20 USDT transfer using TronPy; exact token contract, inventory signer, transfer amount, destination and solid transaction receipt are checked.
- `solana_inventory_payout.py`: locally signed legacy SPL `TransferChecked` for the pinned USDT mint (6 decimals), inventory-owned source ATA, idempotent destination ATA creation, finalized signature and parsed transfer details.
- `inventory_keystore.py` and `inventory_keystore_cli.py`: network-bound encrypted key files (scrypt + XSalsa20-Poly1305), owner-only file permissions, hidden terminal input, and passphrases supplied only through local environment variables. Key material must not be placed in GitHub, API requests, logs, or chat.
- `payout_runtime.py`: creates only adapters explicitly enabled by operator configuration. The executor itself defaults to disabled and requires an explicit runtime enable flag.
- Dependencies and unit/compile checks are declared in `custodial/requirements.txt` and the dedicated CI workflow.

**Release status:** this is code-level implementation under CI validation, not a live-money release. All `featureEnabled` and per-network `enabled` flags remain false. No mainnet transaction has been signed or broadcast by this development work. Before enabling payouts, the operator must import and verify each existing inventory key locally, configure HTTPS RPCs and passphrases on the runtime host, check live inventory balances/fees, and complete small-value controlled live-chain tests with separate explicit approval. The hosted runtime and DEX/API integration are later release steps.


### Local key import (operator machine only)

Run the hidden-input CLI from `cross-chain/custodial`, using a separate file for each network:

```sh
python inventory_keystore_cli.py --network ethereum --file ~/.sobya/keys/ethereum.json
python inventory_keystore_cli.py --network sobya --file ~/.sobya/keys/sobya.json
python inventory_keystore_cli.py --network tron --file ~/.sobya/keys/tron.json
python inventory_keystore_cli.py --network solana --file ~/.sobya/keys/solana.json
```

The CLI asks for the existing wallet private key without echoing it, then asks for a new keystore passphrase twice. It prints only the derived public address. Confirm that address matches the configured inventory address before using the file. The same EVM public address on Ethereum and SOBYA still requires two separately network-bound keystore files. Never upload these files or enter their contents in chat.

At runtime, set each `SOBYA_*_KEYSTORE` variable to its local file path and the matching `SOBYA_*_KEYSTORE_PASSPHRASE` variable in the host's private environment. Set the four `SOBYA_*_RPC_URL` variables to operator-controlled HTTPS RPC endpoints. These variables are deliberately absent from the repository.
