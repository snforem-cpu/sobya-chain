import test from "node:test";
import assert from "node:assert/strict";
import { expectedSoby } from "./worker.mjs";

test("converts six-decimal USDT to 18-decimal SOBY at configured fixed rate", () => {
  assert.equal(expectedSoby(1_000_000n, "25"), 25n * 10n ** 18n);
});

test("rejects non-representable conversion precision", () => {
  assert.throws(() => expectedSoby(1n, "0.000000000000000001"), /represented exactly/);
});

test("rejects zero amounts and zero rate", () => {
  assert.throws(() => expectedSoby(0n, "1"), /positive/);
  assert.throws(() => expectedSoby(1n, "0"), /positive/);
});
