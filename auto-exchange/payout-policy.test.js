import test from "node:test";
import assert from "node:assert/strict";
import { calculateRequiredPayoutBalance, isPayoutEligible } from "./payout-policy.js";

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
test("supports zero-gas-fee SOBYA networks without adding a false gas reserve", () => {
  assert.equal(
    calculateRequiredPayoutBalance({ payoutAmountAtomic: "1000", gasLimit: "21000", maxFeePerGas: "0" }),
    1000n
  );
  assert.throws(() => calculateRequiredPayoutBalance({ payoutAmountAtomic: "1000", gasLimit: "21000", maxFeePerGas: "-1" }));
});


test("only a confirmed paid order without a reserved nonce is payout eligible", () => {
  assert.equal(isPayoutEligible({ status: "paid" }), true);
  assert.equal(isPayoutEligible({ status: "payout_waiting_funds" }), true);
  assert.equal(isPayoutEligible({ status: "payout_prepared", payoutNonce: 4 }), false);
  assert.equal(isPayoutEligible({ status: "payout_broadcast", payoutNonce: 4, payoutTxHash: "0xabc" }), false);
  assert.equal(isPayoutEligible({ status: "paid", payoutNonce: 4 }), false);
  assert.equal(isPayoutEligible({ status: "paid", payoutTxHash: "0xabc" }), false);
  assert.equal(isPayoutEligible({ status: "open" }), false);
});
