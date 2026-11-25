import test from "node:test";
import assert from "node:assert/strict";
import { createReturnQuote, calculateUsdtRefundAtomic, matchSobyReturn } from "./return-ledger.js";

const wallet = "0x1111111111111111111111111111111111111111";
const inventory = "0xebdb899fFE84a89e1d576964b640491c135651AD";
const hash = "0x" + "a".repeat(64);
function ledger() { return { currentPriceUsdtPerSoby: "0.005", returnQuotes: [] }; }

test("return quote reserves a unique exact SOBY amount and calculates net USDT refund", () => {
  const result = createReturnQuote({ ledger: ledger(), issueNumber: 7, sender: wallet, requestedAmount: "100", now: new Date("2026-11-25T10:00:00Z") });
  assert.equal(result.quote.paymentAmountAtomic, (100n * 10n ** 18n + 1n).toString());
  assert.equal(result.quote.payoutAmountAtomic, calculateUsdtRefundAtomic({ sobyAmountAtomic: result.quote.paymentAmountAtomic, priceUsdtPerSoby: "0.005" }).toString());
  assert.equal(result.quote.status, "open");
  assert.equal(createReturnQuote({ ledger: result.ledger, issueNumber: 7, sender: wallet, requestedAmount: "100" }).existing.orderId, result.quote.orderId);
});

test("return matcher requires exact wallet, inventory, amount, quote window and confirmations", () => {
  const q = createReturnQuote({ ledger: ledger(), issueNumber: 8, sender: wallet, requestedAmount: "2", now: new Date("2026-11-25T10:00:00Z") }).quote;
  const transfer = { chainId: 357812033857, txHash: hash, from: wallet, to: inventory,
    amountAtomic: q.paymentAmountAtomic, blockNumber: 100, blockTimestamp: "2026-11-25T10:01:00Z" };
  const pending = matchSobyReturn({ returnQuotes: [q], processedReturns: [], transfer, now: Date.parse("2026-11-25T10:02:00Z"), confirmations: 1, requiredConfirmations: 2 });
  assert.equal(pending.decision, "confirmations_pending");
  const matched = matchSobyReturn({ returnQuotes: [q], processedReturns: [], transfer, now: Date.parse("2026-11-25T10:02:00Z"), confirmations: 2, requiredConfirmations: 2 });
  assert.equal(matched.decision, "matched_returned_not_refunded");
  assert.equal(matched.returnQuotes[0].status, "returned");
  assert.deepEqual(matchSobyReturn({ returnQuotes: matched.returnQuotes, processedReturns: matched.processedReturns, transfer, confirmations: 2, requiredConfirmations: 2 }).decision, "duplicate");
});

test("wrong sender or amount cannot match a return quote", () => {
  const q = createReturnQuote({ ledger: ledger(), issueNumber: 9, sender: wallet, requestedAmount: "2" }).quote;
  const transfer = { chainId: 357812033857, txHash: hash, from: "0x2222222222222222222222222222222222222222",
    to: inventory, amountAtomic: q.paymentAmountAtomic, blockNumber: 101, blockTimestamp: new Date().toISOString() };
  assert.equal(matchSobyReturn({ returnQuotes: [q], processedReturns: [], transfer, confirmations: 2, requiredConfirmations: 2 }).decision, "unmatched");
});
