import test from "node:test";
import assert from "node:assert/strict";
import { Wallet } from "ethers";
import { executeReturnRefund } from "./return-execution.js";

const wallet = "0x1111111111111111111111111111111111111111";
const hash = "0x" + "b".repeat(64);
function fixture({ failFirstBroadcast = false } = {}) {
  const quote = { orderId: "return-1", sender: wallet, status: "returned",
    returnTxHash: hash, returnBlockNumber: 100, paymentAmountAtomic: "2000000000000000000",
    payoutAmountAtomic: "9900000" };
  const ledger = { returnQuotes: [quote], currentPriceUsdtPerSoby: "0.005" };
  let saves = 0;
  let broadcasts = 0;
  const saveLedger = async () => "sha-" + (++saves);
  const refundReceipt = () => ({
    status: 1, blockNumber: 200, gasUsed: 45000n, gasPrice: 10n,
    logs: [{ address: "0xdAC17F958D2ee523a2206206994597C13D831ec7" }]
  });
  const ethereum = {
    sobyaProvider: {
      getTransactionReceipt: async () => ({ status: 1, blockNumber: 100 }),
      getBlockNumber: async () => 102
    },
    getFeeData: async () => ({ gasPrice: 10n }),
    getBalance: async () => 10n ** 18n,
    getTransactionCount: async () => 4,
    getTransactionReceipt: async () => null,
    getTransaction: async () => null,
    broadcastTransaction: async () => {
      broadcasts++;
      if (failFirstBroadcast && broadcasts === 1) throw new Error("simulated network timeout after possible broadcast");
      return { hash: "broadcasted" };
    },
    waitForTransaction: async () => refundReceipt(),
    getBlockNumber: async () => 300
  };
  const transfer = async () => { throw new Error("legacy contract transfer must not be used"); };
  transfer.estimateGas = async () => 50000n;
  const signer = Wallet.createRandom();
  const usdt = {
    balanceOf: async () => 100000000n,
    transfer,
    interface: {
      encodeFunctionData: () => "0xa9059cbb",
      parseLog: () => ({ name: "Transfer", args: {
        from: signer.address,
        to: wallet,
        value: 9899999n
      } })
    }
  };
  const applyConfirmedPriceChange = ({ ledger: l, direction, settlementConfirmed }) => {
    assert.equal(direction, "down");
    assert.equal(settlementConfirmed, true);
    return { ...l, currentPriceUsdtPerSoby: "0.00499" };
  };
  const getEthUsdPrice = async () => "200000000000";
  return { quote, ledger, saveLedger, ethereum, usdt, signer, applyConfirmedPriceChange,
    getEthUsdPrice, get broadcasts() { return broadcasts; } };
}

test("refund persists deterministic signed intent, verifies Transfer event, confirms, and reprices", async () => {
  const f = fixture();
  const result = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(result.completed, true);
  assert.equal(result.ledger.returnQuotes[0].status, "settled");
  assert.equal(result.ledger.returnQuotes[0].refundNonce, 4);
  assert.match(result.ledger.returnQuotes[0].refundTxHash, /^0x[0-9a-f]{64}$/);
  assert.equal(result.ledger.returnQuotes[0].refundTransaction.chainId, 1);
  assert.equal(result.ledger.currentPriceUsdtPerSoby, "0.00499");
  assert.equal(result.ledger.returnQuotes[0].actualRefundAmountAtomic, "9899999");
  assert.equal(result.ledger.returnQuotes[0].estimatedNetworkFeeUsdtAtomic, "1");
  assert.equal(f.broadcasts, 1);
});

test("USDT refund waits for inventory funding and resumes without a new SOBY transfer", async () => {
  const f = fixture();
  f.usdt.balanceOf = async () => 0n;
  const waiting = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(waiting.waitingForFunds, true);
  assert.equal(f.quote.status, "refund_waiting_funds");
  assert.equal(f.quote.refundNonce, undefined);
  f.usdt.balanceOf = async () => 100000000n;
  const resumed = await executeReturnRefund({ ...f, ledgerSha: waiting.ledgerSha,
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(resumed.completed, true);
  assert.equal(f.quote.status, "settled");
});

test("USDT refund waits for ETH gas funding and resumes without a new SOBY transfer", async () => {
  const f = fixture();
  f.ethereum.getBalance = async () => 0n;
  const waiting = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(waiting.waitingForFunds, true);
  assert.equal(f.quote.status, "refund_waiting_funds");
  f.ethereum.getBalance = async () => 10n ** 18n;
  const resumed = await executeReturnRefund({ ...f, ledgerSha: waiting.ledgerSha,
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(resumed.completed, true);
  assert.equal(f.quote.status, "settled");
});

test("successful receipt without exact USDT Transfer event is held for review", async () => {
  const f = fixture();
  f.usdt.interface.parseLog = () => { throw new Error("unrelated log"); };
  const result = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(result.review, true);
  assert.equal(result.completed, false);
  assert.equal(result.ledger.returnQuotes[0].status, "review");
  assert.equal(result.ledger.currentPriceUsdtPerSoby, "0.005");
});

test("return too large to preserve a positive price is rejected before refund", async () => {
  const f = fixture();
  f.quote.paymentAmountAtomic = (500_000_000n * 10n ** 18n).toString();
  await assert.rejects(
    executeReturnRefund({ ...f, ledgerSha: "start", refundRecipient: wallet,
      amount: 9900000n, ethereumConfirmations: 12 }),
    /reduce price to zero or below/
  );
});

test("an old prepared refund without a deterministic transaction intent is not retried", async () => {
  const f = fixture();
  f.quote.refundNonce = 4;
  f.quote.status = "refund_prepared";
  const result = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n });
  assert.equal(result.skipped, true);
  assert.equal(result.completed, false);
  assert.equal(f.broadcasts, 0);
});

test("ambiguous broadcast failure recovers by rebroadcasting the identical signed transaction", async () => {
  const f = fixture({ failFirstBroadcast: true });
  await assert.rejects(
    executeReturnRefund({ ...f, ledgerSha: "start", refundRecipient: wallet,
      amount: 9900000n, ethereumConfirmations: 12 }),
    /simulated network timeout/
  );
  assert.equal(f.quote.status, "refund_prepared");
  const originalHash = f.quote.refundTxHash;
  const originalNonce = f.quote.refundNonce;
  const resumed = await executeReturnRefund({ ...f, ledgerSha: "sha-1",
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(resumed.completed, true);
  assert.equal(f.quote.refundTxHash, originalHash);
  assert.equal(f.quote.refundNonce, originalNonce);
  assert.equal(f.broadcasts, 2);
});
