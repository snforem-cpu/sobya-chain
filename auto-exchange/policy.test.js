import test from "node:test";
import assert from "node:assert/strict";
import { AUTO_EXCHANGE_POLICY, getDirectionalPriceCoefficient } from "./config.js";

test("opening sale policy is fixed", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby, "0.005");
  assert.equal(AUTO_EXCHANGE_POLICY.referenceInventorySoby, 1_000_000);
  assert.equal(AUTO_EXCHANGE_POLICY.exchangeFeeBps, 100);
  assert.equal(AUTO_EXCHANGE_POLICY.quoteValiditySeconds, 600);
});

test("upward and downward coefficients are 100 and 25 with 4:1 asymmetry", () => {
  assert.equal(getDirectionalPriceCoefficient("up"), 100);
  assert.equal(getDirectionalPriceCoefficient("down"), 25);
  assert.equal(getDirectionalPriceCoefficient("up") / getDirectionalPriceCoefficient("down"), 4);
  assert.equal(AUTO_EXCHANGE_POLICY.priceImpactDenominator, 10_000);
});

test("price has no configured ceiling and does not move with time alone", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.maxPrice, null);
  assert.equal(AUTO_EXCHANGE_POLICY.timeOnlyPriceChanges, false);
  assert.equal(AUTO_EXCHANGE_POLICY.priceChangesRequireConfirmedTrades, true);
});

test("the same inventory EVM address is configured for Ethereum and SOBYA", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress, "0xebdb899fFE84a89e1d576964b640491c135651AD");
  assert.equal(AUTO_EXCHANGE_POLICY.ethereumChainId, 1);
  assert.equal(AUTO_EXCHANGE_POLICY.sobyaEvmChainId, 357812033857);
});

test("real transfers remain disabled until settlement safeguards are implemented", () => {
  assert.equal(AUTO_EXCHANGE_POLICY.tradingEnabled, false);
  assert.equal(AUTO_EXCHANGE_POLICY.payoutEnabled, false);
});
