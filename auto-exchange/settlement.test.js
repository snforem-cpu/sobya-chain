import test from "node:test";
import assert from "node:assert/strict";
import { matchDeposit, validateQuote } from "./settlement.js";

const quote = {
  orderId: "sobya-order-0001",
  sender: "0x1111111111111111111111111111111111111111",
  depositAddress: "0xebdb899fFE84a89e1d576964b640491c135651AD",
  tokenAddress: "0x2222222222222222222222222222222222222222",
  chainId: 1,
  paymentAmountAtomic: "10000000",
  payoutAmountAtomic: "1980000000000000000000",
  createdAt: "2026-11-25T10:00:00.000Z",
  expiresAt: "2026-11-25T10:10:00.000Z",
  status: "open"
};
const transfer = {
  txHash: "0x"+"a".repeat(64), logIndex: 0, chainId: 1,
  from: quote.sender, to: quote.depositAddress, tokenAddress: quote.tokenAddress,
  amountAtomic: quote.paymentAmountAtomic,
  blockTimestamp: "2026-11-25T10:05:00.000Z"
};
const base = { quotes: [quote], processedTransfers: [], transfer,
  now: Date.parse("2026-11-25T10:06:00.000Z"), confirmations: 12, requiredConfirmations: 12 };

test("validates a fully specified quote", () => assert.equal(validateQuote(quote), true));
test("rejects non-atomic decimal payment amounts", () => {
  assert.throws(() => validateQuote({ ...quote, paymentAmountAtomic: "10.5" }));
});
test("exact unique quote match becomes paid but never settled", () => {
  const result = matchDeposit(base);
  assert.equal(result.decision, "matched_paid_not_settled");
  assert.equal(result.quotes[0].status, "paid");
  assert.equal(result.payoutRecipient, quote.sender);
  assert.equal(result.payoutAmountAtomic, quote.payoutAmountAtomic);
  assert.equal(result.processedTransfers.length, 1);
});
test("rejects wrong amount, sender, token, recipient, or chain as unmatched", () => {
  for (const patch of [
    { amountAtomic: "10000001" }, { from: "0x3333333333333333333333333333333333333333" },
    { tokenAddress: "0x4444444444444444444444444444444444444444" },
    { to: "0x5555555555555555555555555555555555555555" }, { chainId: 5 }
  ]) assert.equal(matchDeposit({ ...base, transfer: { ...transfer, ...patch } }).decision, "unmatched");
});
test("does not match a payment mined outside quote validity", () => {
  assert.equal(matchDeposit({ ...base, transfer: { ...transfer,
    blockTimestamp: "2026-11-25T10:10:01.000Z" } }).decision, "expired");
});
test("waits for required confirmations", () => {
  assert.equal(matchDeposit({ ...base, confirmations: 11 }).decision, "confirmations_pending");
});
test("detects duplicate transaction logs", () => {
  assert.equal(matchDeposit({ ...base, processedTransfers: ["1:"+transfer.txHash+":0"] }).decision, "duplicate");
});
test("ambiguous open quotes never auto-match", () => {
  assert.equal(matchDeposit({ ...base, quotes: [quote, { ...quote, orderId: "sobya-order-0002" }] }).decision, "ambiguous");
});
test("unmatched or pending transfers do not mutate ledger", () => {
  const result = matchDeposit({ ...base, confirmations: 1,
    quotes: [{ ...quote, paymentAmountAtomic: "7" }] });
  assert.equal(result.decision, "unmatched");
  assert.equal(result.quotes[0].status, "open");
  assert.deepEqual(result.processedTransfers, []);
});

test("validates persisted payout lifecycle states", () => {
  assert.equal(validateQuote({ ...quote, status: "payout_prepared" }), true);
  assert.equal(validateQuote({ ...quote, status: "payout_broadcast" }), true);
});
test("matcher fails closed when any persisted quote is malformed", () => {
  assert.throws(() => matchDeposit({ ...base, quotes: [{ ...quote, paymentAmountAtomic: "1.2" }] }));
});
test("matcher rejects malformed transfer fields", () => {
  assert.throws(() => matchDeposit({ ...base, transfer: { ...transfer, amountAtomic: "1.2" } }));
});
