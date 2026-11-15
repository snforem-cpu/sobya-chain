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
  ceilingPriceUsd: 0.02,
};

test("returns the opening reference price at neutral baseline", () => {
  assert.equal(calculateDynamicPrice(policy), 0.005);
});

test("inventory depletion increases the target price", () => {
  const next = calculateDynamicPrice({ ...policy, previousPriceUsd: 0.005, availableInventory: 500_000 });
  assert.ok(next > 0.005);
});

test("a demand decline reduces price gradually, not abruptly", () => {
  const next = calculateDynamicPrice({
    ...policy,
    previousPriceUsd: 0.006,
    verifiedDemand24h: 0,
    upwardSmoothing: 0.5,
    downwardSmoothing: 0.1,
  });
  assert.ok(next < 0.006);
  assert.ok(next > 0.005);
});

test("rejects inventory values outside configured range", () => {
  assert.throws(() => calculateDynamicPrice({ ...policy, availableInventory: 1_000_001 }), RangeError);
});

test("rejects invalid bounds", () => {
  assert.throws(() => calculateDynamicPrice({ ...policy, floorPriceUsd: 0.03, ceilingPriceUsd: 0.02 }), RangeError);
});
