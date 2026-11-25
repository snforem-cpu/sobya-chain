import test from "node:test";
import assert from "node:assert/strict";
import { executeReturnRefund } from "./return-execution.js";

const wallet = "0x1111111111111111111111111111111111111111";
const hash = "0x" + "b".repeat(64);
function fixture() {
  const quote = { orderId: "return-1", sender: wallet, status: "returned",
    returnTxHash: hash, returnBlockNumber: 100, paymentAmountAtomic: "2000000000000000000",
    payoutAmountAtomic: "9900000" };
  const ledger = { returnQuotes: [quote], currentPriceUsdtPerSoby: "0.005" };
  let saves = 0;
  const saveLedger = async () => "sha-" + (++saves);
  const ethereum = { sobyaProvider: {
    getTransactionReceipt: async () => ({ status: 1, blockNumber: 100 }),
    getBlockNumber: async () => 102
  }, getFeeData: async () => ({ gasPrice: 10n }),
  getBalance: async () => 10n ** 18n,
  getTransactionCount: async () => 4 };
  const transfer = async (_to, _amount, opts) => {
    assert.equal(opts.nonce, 4);
    return { hash: "0x" + "c".repeat(64), wait: async () => ({
      status: 1, blockNumber: 200, gasUsed: 45000n, gasPrice: 10n,
      logs: [{ address: "0xdAC17F958D2ee523a2206206994597C13D831ec7" }]
    }) };
  };
  transfer.estimateGas = async () => 50000n;
  const usdt = { balanceOf: async () => 100000000n, transfer,
    interface: { parseLog: () => ({ name: "Transfer", args: {
      from: "0xebdb899fFE84a89e1d576964b640491c135651AD",
      to: wallet, value: 9900000n
    } }) } };
  const signer = { address: "0xebdb899fFE84a89e1d576964b640491c135651AD" };
  const applyConfirmedPriceChange = ({ ledger: l, direction, settlementConfirmed }) => {
    assert.equal(direction, "down");
    assert.equal(settlementConfirmed, true);
    return { ...l, currentPriceUsdtPerSoby: "0.00499" };
  };
  return { quote, ledger, saveLedger, ethereum, usdt, signer, applyConfirmedPriceChange };
}

test("refund reserves nonce, verifies exact Transfer event, confirms, then applies downward price change", async () => {
  const f = fixture();
  const result = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n, ethereumConfirmations: 12 });
  assert.equal(result.completed, true);
  assert.equal(result.ledger.returnQuotes[0].status, "settled");
  assert.equal(result.ledger.returnQuotes[0].refundNonce, 4);
  assert.equal(result.ledger.returnQuotes[0].refundTxHash, "0x" + "c".repeat(64));
  assert.equal(result.ledger.currentPriceUsdtPerSoby, "0.00499");
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

test("prepared refund cannot be blindly retried", async () => {
  const f = fixture();
  f.quote.refundNonce = 4;
  const result = await executeReturnRefund({ ...f, ledgerSha: "start",
    refundRecipient: wallet, amount: 9900000n });
  assert.equal(result.skipped, true);
  assert.equal(result.completed, false);
});
