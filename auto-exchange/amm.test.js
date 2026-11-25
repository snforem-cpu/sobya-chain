import test from "node:test";
import assert from "node:assert/strict";
import { quoteExactInput, quoteBuySoby, quoteSellSoby } from "./amm.js";

const USDT = 10n ** 6n;
const SOBY = 10n ** 18n;

test("constant-product quote returns output and post-trade reserves", () => {
  const q = quoteBuySoby({
    usdtInAtomic: 100n * USDT,
    usdtReserveAtomic: 5_000n * USDT,
    sobyReserveAtomic: 1_000_000n * SOBY
  });
  assert.equal(BigInt(q.amountOut) > 0n, true);
  assert.equal(BigInt(q.reserveInAfter), 5_100n * USDT);
  assert.equal(BigInt(q.reserveOutAfter), 1_000_000n * SOBY - BigInt(q.amountOut));
  assert.equal(q.feeBps, "100");
  assert.equal(BigInt(q.priceImpactBps) > 0n, true);
});

test("larger buy has greater price impact than smaller buy", () => {
  const small = quoteBuySoby({
    usdtInAtomic: 10n * USDT,
    usdtReserveAtomic: 5_000n * USDT,
    sobyReserveAtomic: 1_000_000n * SOBY
  });
  const large = quoteBuySoby({
    usdtInAtomic: 1_000n * USDT,
    usdtReserveAtomic: 5_000n * USDT,
    sobyReserveAtomic: 1_000_000n * SOBY
  });
  assert.equal(BigInt(large.priceImpactBps) > BigInt(small.priceImpactBps), true);
});

test("sell path uses SOBY input reserve and USDT output reserve", () => {
  const q = quoteSellSoby({
    sobyInAtomic: 10_000n * SOBY,
    sobyReserveAtomic: 1_000_000n * SOBY,
    usdtReserveAtomic: 5_000n * USDT
  });
  assert.equal(BigInt(q.amountOut) > 0n, true);
  assert.equal(BigInt(q.reserveInAfter), 1_010_000n * SOBY);
  assert.equal(BigInt(q.reserveOutAfter) < 5_000n * USDT, true);
});

test("minimum output protects users from excessive slippage", () => {
  assert.throws(() => quoteBuySoby({
    usdtInAtomic: 100n * USDT,
    usdtReserveAtomic: 5_000n * USDT,
    sobyReserveAtomic: 1_000_000n * SOBY,
    minSobyOutAtomic: 1_000_000n * SOBY
  }), /below minAmountOut/);
});

test("invalid reserves, zero input, and impossible fees are rejected", () => {
  assert.throws(() => quoteExactInput({ amountIn: 0n, reserveIn: 1n, reserveOut: 1n }));
  assert.throws(() => quoteExactInput({ amountIn: 1n, reserveIn: 0n, reserveOut: 1n }));
  assert.throws(() => quoteExactInput({ amountIn: 1n, reserveIn: 1n, reserveOut: 1n, feeBps: 10_000 }));
});
