# SOBYA cross-chain automation without Enzonic

## Architecture

This is a staged replacement for the Enzonic-hosted custodial API. It is not live
and must not accept customer funds until every deployment and end-to-end gate below
has passed.

1. The DEX frontend connects to MetaMask.
2. On Ethereum, the buyer approves the canonical USDT contract and calls
   `SobyaCrossChainDeposit.deposit`. The contract escrows the exact USDT amount
   and emits an order-bound event containing the recipient and SOBY payout amount.
3. A scheduled GitHub Actions worker reads finalized deposit events from Ethereum.
   It must verify chain ID, contract address, event arguments, confirmations,
   unique order ID, and the configured price/size policy.
4. The worker submits a payout to `SobyaInventoryPayoutVault.release` on SOBYA.
   The vault rejects duplicate order IDs and enforces per-order and daily caps.
5. After the SOBYA payout is finalized, the worker calls `markFulfilled` on the
   Ethereum escrow, then releases the escrowed USDT to the configured treasury.
6. If an order is not fulfilled before its on-chain deadline, the depositor can
   reclaim the escrowed USDT.

## Important limits

- GitHub Actions is a scheduled/ephemeral worker, not a permanent HTTP API.
  It cannot directly replace the quote/order HTTP API with identical real-time
  behavior. Quotes must be calculated in the client from published, bounded
  parameters or supplied by an on-chain quote contract.
- Scheduled Actions may be delayed. The product must display that settlement is
  asynchronous and never promise instant execution.
- This first contract pair supports Ethereum ERC-20 deposits (initially USDT)
  and native SOBY payouts on SOBYA EVM. It does not automatically support ETH,
  BNB, Solana, TRON, or arbitrary assets.
- The automation relayer key must be a dedicated, low-balance key stored only
  as a GitHub Actions secret. Do not use the owner's primary wallet key. The
  Ethereum operator key should also be separate and tightly funded.
- A public repository must never contain private keys, keystore files,
  passphrases, RPC credentials, or GitHub tokens.
- The escrow contract's operator is a trust role: it can mark a deposit fulfilled
  and release the payment. The payout vault's owner can change the relayer and
  limits. These contracts require independent security review before mainnet use.

## Deployment and release gates

1. Run Foundry unit, fuzz, and invariant tests for both contracts.
2. Review the contracts independently; test USDT behavior on an Ethereum fork.
3. Deploy the escrow to Ethereum with canonical USDT and a dedicated operator.
4. Deploy the payout vault to SOBYA EVM; fund it only with a small controlled
   test inventory and configure a dedicated relayer.
5. Implement and test a stateless event scanner with durable checkpointing and
   replay-safe transaction recovery. The checkpoint must not be stored only on
   an ephemeral runner filesystem. A first implementation now exists under
   `cross-chain/github-actions-worker/` and stores its cursor on the
   `sobya-crosschain-state` branch.
6. Add a GitHub Actions scheduled workflow with concurrency protection, bounded
   block ranges, retry/recovery, finality checks, and secret-only signing. A
   disabled-by-default workflow now exists at
   `.github/workflows/crosschain-settlement.yml`; it can run the settlement job
   only from `main` after the repository variable `CROSSCHAIN_AUTOMATION_ENABLED`
   is explicitly enabled.
7. Complete a low-value end-to-end test: USDT deposit -> finalized SOBY payout
   -> escrow fulfillment -> USDT release. Also test expiry/refund and duplicate
   event replay.
8. Only then enable the DEX UI and publish verified deployment addresses.

No mainnet deployment, customer-deposit enablement, or wallet signing is performed
by adding these source files.
