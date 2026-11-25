import test from "node:test";
import assert from "node:assert/strict";
import { AUTO_EXCHANGE_POLICY, getDirectionalPriceCoefficient } from "./config.js";

test("opening sale policy is fixed", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby, 0.005);
  assert.equal(AUTO_EXCHANGE_POLICY.referenceInventorySoby, 1_000_000);
  assert.equal(AUTO_EXCHANGE_POLICY.exchangeFeeBps, 100);
  assert.equal(AUTO_EXCHANGE_POLICY.quoteValiditySeconds, 600);
});

test("upward price response is four times downward response", () => {
  assert.equal(getDirectionalPriceCoefficient("up"), 1000);
  assert.equal(getDirectionalPriceCoefficient("down"), 250);
  assert.equal(getDirectionalPriceCoefficient("up") / getDirectionalPriceCoefficient("down"), 4);
});

test("price has no configured ceiling and does not move with time alone", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.maxPrice, null);
  assert.equal(AUTO_EXCHANGE_POLICY.timeOnlyPriceChanges, false);
  assert.equal(AUTO_EXCHANGE_POLICY.priceChangesRequireConfirmedTrades, true);
});

test("real transfers remain disabled until settlement safeguards are implemented", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.tradingEnabled, false);
  assert.equal(AUTO_EXCHANGE_POLICY.payoutEnabled, false);
});
