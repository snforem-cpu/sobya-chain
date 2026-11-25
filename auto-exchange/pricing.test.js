import test from "node:test";
import assert from "node:assert/strict";
import { calculateNextPrice, applyConfirmedPriceChange, parsePriceAtomic } from "./pricing.js";

const scale = 10n ** 18n;

test("10,000 SOBY sold raises 0.005 price by exactly 0.01 percent", () => {
  const next = calculateNextPrice({ currentPrice: "0.005", quantitySobyAtomic: 10_000n * scale, direction: "up" });
  assert.equal(next, parsePriceAtomic("0.0050005"));
});

test("10,000 SOBY returned lowers 0.005 price by exactly 0.0025 percent", () => {
  const next = calculateNextPrice({ currentPrice: "0.005", quantitySobyAtomic: 10_000n * scale, direction: "down" });
  assert.equal(next, parsePriceAtomic("0.004999875"));
});

test("price movement keeps the four-to-one directional ratio", () => {
  const up = calculateNextPrice({ currentPrice: "1", quantitySobyAtomic: 10_000n * scale, direction: "up" });
  const down = calculateNextPrice({ currentPrice: "1", quantitySobyAtomic: 10_000n * scale, direction: "down" });
  assert.equal((up - scale) * 4n, (scale - down) * 1n * 4n);
});

test("price cannot change without confirmed settlement", () => {
  assert.throws(() => applyConfirmedPriceChange({
    ledger: { quotes: [] }, quantitySobyAtomic: scale, direction: "up", settlementConfirmed: false
  }), /confirmed settlement/);
});

test("confirmed price change is persisted in returned ledger", () => {
  const ledger = { quotes: [] };
  const next = applyConfirmedPriceChange({
    ledger, quantitySobyAtomic: 10_000n * scale, direction: "up", settlementConfirmed: true
  });
  assert.equal(next.currentPriceUsdtPerSoby, "0.0050005");
  assert.equal(ledger.currentPriceUsdtPerSoby, undefined);
});
