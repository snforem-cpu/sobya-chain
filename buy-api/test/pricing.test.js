import test from "node:test";
import assert from "node:assert/strict";
import { calculateDynamicPrice } from "../src/pricing.js";

const policy = {
  referencePriceUsd: 0.005,
  previousPriceUsd: 0.005,
  availableInventory: 1_000_000,
  initialInventory: 1_000_000,
  verifiedDemand24h: 100,
  baselineDemand24h: 100,
  inventoryWeight: 0.25,
  demandWeight: 0.1,
  upwardSmoothing: 0.5,
  downwardSmoothing: 0.1,
  floorPriceUsd: 0.0025,
};

test("returns the opening reference price at neutral baseline", () => {
  assert.equal(calculateDynamicPrice(policy), 0.005);
});

test("inventory depletion increases the target price", () => {
  const next = calculateDynamicPrice({ ...policy, availableInventory: 500_000 });
  assert.ok(next > 0.005);
});

test("strong verified demand can raise price without an artificial ceiling", () => {
  const next = calculateDynamicPrice({
    ...policy,
    verifiedDemand24h: 100_000,
    previousPriceUsd: 10,
  });
  assert.ok(next > 10);
});

test("a demand decline never lowers the last reached price", () => {
  const next = calculateDynamicPrice({
    ...policy,
    previousPriceUsd: 0.006,
    verifiedDemand24h: 0,
    upwardSmoothing: 0.5,
    downwardSmoothing: 0.1,
  });
  assert.equal(next, 0.006);
});

test("enforces the minimum price without imposing a maximum", () => {
  const low = calculateDynamicPrice({
    ...policy,
    previousPriceUsd: 0.003,
    verifiedDemand24h: 0,
    floorPriceUsd: 0.0025,
  });
  assert.ok(low >= 0.0025);

  const high = calculateDynamicPrice({
    ...policy,
    previousPriceUsd: 100,
    verifiedDemand24h: 100_000,
  });
  assert.ok(high > 100);
});

test("rejects inventory values outside configured range", () => {
  assert.throws(() => calculateDynamicPrice({ ...policy, availableInventory: 1_000_001 }), RangeError);
});

test("rejects non-positive minimum price", () => {
  assert.throws(() => calculateDynamicPrice({ ...policy, floorPriceUsd: 0 }), RangeError);
});
