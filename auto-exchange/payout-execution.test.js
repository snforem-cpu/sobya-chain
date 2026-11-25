import test from "node:test";
import assert from "node:assert/strict";
import { executePayout } from "./payout-execution.js";

function fixture(overrides = {}) {
  const quote = {
    orderId: "sobya-e2e-1", status: "paid",
    sender: "0x2222222222222222222222222222222222222222",
    depositAddress: "0x3333333333333333333333333333333333333333",
    tokenAddress: "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    chainId: 1, paymentAmountAtomic: "1000000", payoutAmountAtomic: "100000",
    createdAt: "2026-11-25T10:00:00.000Z", expiresAt: "2026-11-25T10:10:00.000Z"
  };
  const ledger = { quotes: [quote], priceState: { marker: "unchanged" } };
  const saves = [];
  const sobya = {
    estimateGas: async () => 21_000n,
    getFeeData: async () => ({ maxFeePerGas: 2n, maxPriorityFeePerGas: 1n, gasPrice: null }),
    getBalance: async () => 1_000_000n,
    getTransactionCount: async () => 7
  };
  const signer = {
    address: "0x1111111111111111111111111111111111111111",
    sendTransaction: async request => {
      assert.equal(request.nonce, 7);
      assert.equal(request.value, 49_600n);
      return {
        hash: "0x" + "a".repeat(64),
        wait: async confirmations => {
          assert.equal(confirmations, 2);
          return { status: 1, blockNumber: 123, gasUsed: 21_000n, gasPrice: 2n };
        }
      };
    }
  };
  const deps = {
    ledger, quote, ledgerSha: "initial-sha", sobya, signer,
    payoutRecipient: quote.sender,
    amount: 100_000n,
    saveLedger: async (nextLedger, sha, message) => {
      saves.push({ snapshot: structuredClone(nextLedger), message });
      return "sha-" + saves.length;
    },
    applyConfirmedPriceChange: ({ ledger: current, quantitySobyAtomic, settlementConfirmed }) => {
      assert.ok(["49600", "100000"].includes(quantitySobyAtomic));
      assert.equal(settlementConfirmed, true);
      return { ...current, priceState: { marker: "changed-after-confirmation" } };
    },
    ...overrides
  };
  return { quote, ledger, saves, sobya, signer, deps };
}

test("executes a SOBYA payout when the verified network gas price is zero", async () => {
  const { quote, deps } = fixture({
    sobya: {
      estimateGas: async () => 21_000n,
      getFeeData: async () => ({ maxFeePerGas: null, maxPriorityFeePerGas: null, gasPrice: 0n }),
      getBalance: async () => 1_000_000n,
      getTransactionCount: async () => 8
    },
    signer: {
      address: "0x1111111111111111111111111111111111111111",
      sendTransaction: async request => {
        assert.equal(request.gasPrice, 0n);
        return {
          hash: "0x" + "d".repeat(64),
          wait: async () => ({ status: 1, blockNumber: 125, gasUsed: 21_000n, gasPrice: 0n })
        };
      }
    }
  });
  const result = await executePayout(deps);
  assert.equal(result.completed, true);
  assert.equal(quote.status, "settled");
  assert.equal(quote.payoutFeePaidAtomic, "0");
});

test("executes and persists prepared, broadcast, and confirmed settlement lifecycle", async () => {
  const { quote, saves, deps } = fixture();
  const result = await executePayout(deps);
  assert.equal(result.completed, true);
  assert.equal(result.ledgerSha, "sha-3");
  assert.equal(result.ledger.quotes[0].status, "settled");
  assert.equal(result.ledger.quotes[0].payoutNonce, 7);
  assert.equal(result.ledger.quotes[0].payoutTxHash, "0x" + "a".repeat(64));
  assert.equal(result.ledger.quotes[0].payoutBlockNumber, 123);
  assert.equal(result.ledger.quotes[0].payoutFeePaidAtomic, "42000");
  assert.equal(result.ledger.quotes[0].payoutNetAmountAtomic, "49600");
  assert.equal(result.ledger.quotes[0].payoutNetworkFeeBudgetAtomic, "50400");
  assert.equal(result.ledger.priceState.marker, "changed-after-confirmation");
  assert.deepEqual(saves.map(x => x.snapshot.quotes[0].status),
    ["payout_prepared", "payout_broadcast", "settled"]);
});

test("crash after nonce reservation cannot cause a second signature or broadcast", async () => {
  const { quote, deps } = fixture({
    signer: { address: "0x1111111111111111111111111111111111111111",
      sendTransaction: async () => { throw new Error("simulated process interruption"); } }
  });
  await assert.rejects(() => executePayout(deps), /simulated process interruption/);
  assert.equal(quote.status, "payout_prepared");
  assert.equal(quote.payoutNonce, 7);
  let sendAttempts = 0;
  deps.signer.sendTransaction = async () => { sendAttempts++; };
  const retry = await executePayout(deps);
  assert.equal(retry.skipped, true);
  assert.equal(sendAttempts, 0);
});

test("crash after broadcast cannot create a replacement transaction", async () => {
  const { quote, deps } = fixture({
    signer: { address: "0x1111111111111111111111111111111111111111",
      sendTransaction: async () => ({
        hash: "0x" + "b".repeat(64),
        wait: async () => { throw new Error("simulated wait interruption"); }
      }) }
  });
  await assert.rejects(() => executePayout(deps), /simulated wait interruption/);
  assert.equal(quote.status, "payout_broadcast");
  assert.equal(quote.payoutTxHash, "0x" + "b".repeat(64));
  let sendAttempts = 0;
  deps.signer.sendTransaction = async () => { sendAttempts++; };
  assert.equal((await executePayout(deps)).skipped, true);
  assert.equal(sendAttempts, 0);
});

test("insufficient payout inventory is held safely and resumes automatically after funding", async () => {
  const { quote, deps, saves } = fixture({
    sobya: {
      estimateGas: async () => 21_000n,
      getFeeData: async () => ({ maxFeePerGas: 2n, maxPriorityFeePerGas: 1n, gasPrice: null }),
      getBalance: async () => 1n,
      getTransactionCount: async () => { throw new Error("must not reserve nonce"); }
    }
  });
  const result = await executePayout(deps);
  assert.equal(result.waitingForFunds, true);
  assert.equal(quote.status, "payout_waiting_funds");
  assert.equal(quote.payoutNonce, undefined);
  assert.equal(saves.length, 1);
  deps.sobya.getBalance = async () => 1_000_000n;
  deps.sobya.getTransactionCount = async () => 7;
  const resumed = await executePayout(deps);
  assert.equal(resumed.completed, true);
  assert.equal(quote.status, "settled");
});

test("failed payout receipt is recorded for review and does not move price", async () => {
  const { quote, deps, saves } = fixture({
    signer: { address: "0x1111111111111111111111111111111111111111",
      sendTransaction: async () => ({
        hash: "0x" + "c".repeat(64),
        wait: async () => ({ status: 0, blockNumber: 124, gasUsed: 21_000n, gasPrice: 2n })
      }) },
    applyConfirmedPriceChange: () => { throw new Error("price must not move on failed receipt"); }
  });
  const result = await executePayout(deps);
  assert.equal(result.review, true);
  assert.equal(quote.status, "review");
  assert.equal(saves.at(-1).snapshot.quotes[0].status, "review");
});

test("refuses a quote not owned by the durable ledger", async () => {
  const { deps } = fixture();
  deps.quote = { orderId: "foreign", status: "paid" };
  await assert.rejects(() => executePayout(deps), /must belong to the supplied ledger/);
});

test("refuses a payout recipient that differs from the quote wallet", async () => {
  const { deps } = fixture({ payoutRecipient: "0x4444444444444444444444444444444444444444" });
  await assert.rejects(() => executePayout(deps), /must exactly match the quote sender/);
});

test("refuses a payout amount that differs from the quoted SOBY amount", async () => {
  const { deps } = fixture({ amount: 100_001n });
  await assert.rejects(() => executePayout(deps), /must exactly match the quoted atomic SOBY amount/);
});
