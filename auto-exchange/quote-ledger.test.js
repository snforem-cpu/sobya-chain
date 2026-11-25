import test from "node:test";
import assert from "node:assert/strict";
import { allocateUniquePaymentAmount, calculateOpeningQuote, createQuote, formatUsdtAtomic, parseQuoteIssueBody, parseUsdtAtomic } from "./quote-ledger.js";

const empty = { schemaVersion: 1, quotes: [], processedTransfers: [] };
const sender = "0x1111111111111111111111111111111111111111";

test("parses exact six-decimal USDT amounts", () => {
  assert.equal(parseUsdtAtomic("12.345678"), 12345678n);
  assert.equal(formatUsdtAtomic(12345678n), "12.345678");
  assert.throws(() => parseUsdtAtomic("1.0000001"));
  assert.throws(() => parseUsdtAtomic("0"));
});
test("opening quote applies the configured 1 percent fee", () => {
  assert.equal(calculateOpeningQuote(10_000_000n), 1980n * 10n ** 18n);
});
test("quote calculation uses the current persisted price", () => {
  assert.equal(calculateOpeningQuote(10_000_000n, "0.0050005"), 1979802019798020197980n);
});
test("allocates unique exact payment amount across the complete ledger", () => {
  assert.equal(allocateUniquePaymentAmount(10_000_000n, []).paymentAmountAtomic, "10000001");
  assert.equal(allocateUniquePaymentAmount(10_000_000n, [{paymentAmountAtomic:"10000001"}]).paymentAmountAtomic, "10000002");
});
test("creates quote with unique payment amount and ten-minute expiry", () => {
  const result = createQuote({ ledger: empty, issueNumber: 42, sender, requestedAmount: "10", now: new Date("2026-11-25T10:00:00Z") });
  assert.equal(result.quote.paymentAmountAtomic, "10000001");
  assert.equal(result.quote.payoutAmountAtomic, "1980000198000000000000");
  assert.equal(result.quote.quotedPrice, "0.005");
  assert.equal(Date.parse(result.quote.expiresAt)-Date.parse(result.quote.createdAt), 600000);
  assert.equal(result.ledger.quotes.length, 1);
});
test("creates quote using ledger current price when set", () => {
  const result = createQuote({
    ledger: { ...empty, currentPriceUsdtPerSoby: "0.0050005" },
    issueNumber: 43, sender, requestedAmount: "10", now: new Date("2026-11-25T10:00:00Z")
  });
  assert.equal(result.quote.quotedPrice, "0.0050005");
  assert.equal(result.quote.payoutAmountAtomic, "1979802217778222177782");
});
test("reprocessing the same issue is idempotent", () => {
  const first = createQuote({ledger:empty,issueNumber:7,sender,requestedAmount:"5",now:new Date("2026-11-25T10:00:00Z")});
  const second = createQuote({ledger:first.ledger,issueNumber:7,sender,requestedAmount:"5",now:new Date("2026-11-25T10:01:00Z")});
  assert.equal(second.existing.orderId,first.quote.orderId);
  assert.equal(second.ledger.quotes.length,1);
});
test("expired historical payment amounts are never reused", () => {
  assert.equal(allocateUniquePaymentAmount(10_000_000n,[{paymentAmountAtomic:"10000001",status:"expired"}]).paymentAmountAtomic,"10000002");
});
test("unique USDT routing tail is capped at 0.001 USDT", () => {
  const used = Array.from({ length: 1000 }, (_, i) => ({
    paymentAmountAtomic: String(10_000_001 + i)
  }));
  assert.throws(() => allocateUniquePaymentAmount(10_000_000n, used), /No unique USDT micro-amount/);
});
test("parses GitHub issue form fields", () => {
  assert.deepEqual(parseQuoteIssueBody("### EVM wallet address\n\n"+sender+"\n\n### Requested USDT amount\n\n10.25"),{sender,requestedAmount:"10.25"});
});
test("rejects malformed issue bodies", () => assert.throws(()=>parseQuoteIssueBody("text only")));
