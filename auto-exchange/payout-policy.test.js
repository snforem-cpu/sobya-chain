import test from "node:test";
import assert from "node:assert/strict";
import { calculateRequiredPayoutBalance } from "./payout-policy.js";

test("requires payout plus a 20% buffered gas reserve", () => {
  assert.equal(
    calculateRequiredPayoutBalance({ payoutAmountAtomic: "1000", gasLimit: "21000", maxFeePerGas: "2" }),
    51_400n
  );
});
test("rounds a fractional buffered gas reserve up", () => {
  assert.equal(
    calculateRequiredPayoutBalance({ payoutAmountAtomic: "1", gasLimit: "1", maxFeePerGas: "1" }),
    3n
  );
});
test("rejects zero or negative funding inputs", () => {
  assert.throws(() => calculateRequiredPayoutBalance({ payoutAmountAtomic: "0", gasLimit: "1", maxFeePerGas: "1" }));
});
