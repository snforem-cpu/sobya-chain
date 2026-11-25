// Constant-product AMM quote math for the isolated SOBYA exchange.
// This module is math only: it does not custody funds, submit transactions, or
// persist reserves. Callers must supply verified on-chain reserves and must
// update them only after both sides of a trade are irreversibly settled.

const BPS = 10_000n;

function positive(value, name) {
  const n = BigInt(value);
  if (n <= 0n) throw new RangeError(name + " must be positive");
  return n;
}

/**
 * Exact-input constant-product quote.
 * amountIn, reserveIn, reserveOut and minAmountOut use the same atomic units
 * as their respective input/output tokens.
 */
export function quoteExactInput({
  amountIn,
  reserveIn,
  reserveOut,
  feeBps = 100,
  minAmountOut = 0n
}) {
  const input = positive(amountIn, "amountIn");
  const rin = positive(reserveIn, "reserveIn");
  const rout = positive(reserveOut, "reserveOut");
  const minimum = BigInt(minAmountOut);
  const fee = BigInt(feeBps);
  if (fee < 0n || fee >= BPS) throw new RangeError("feeBps must be between 0 and 9999");
  if (minimum < 0n) throw new RangeError("minAmountOut cannot be negative");

  const inputAfterFee = input * (BPS - fee);
  const output = (inputAfterFee * rout) / (rin * BPS + inputAfterFee);
  if (output <= 0n || output >= rout) throw new RangeError("trade output is zero or exhausts pool reserve");
  if (output < minimum) throw new RangeError("quoted output is below minAmountOut");

  // Price impact compares the effective execution rate (including fee) to
  // the pre-trade spot rate. Integer BPS; no floating-point arithmetic.
  const executionVsSpotBps = (output * rin * BPS) / (input * rout);
  const priceImpactBps = executionVsSpotBps >= BPS ? 0n : BPS - executionVsSpotBps;

  return Object.freeze({
    amountIn: input.toString(),
    amountOut: output.toString(),
    feeBps: fee.toString(),
    reserveInAfter: (rin + input).toString(),
    reserveOutAfter: (rout - output).toString(),
    priceImpactBps: priceImpactBps.toString()
  });
}

/** USDT (6 decimals) -> SOBY (18 decimals), with verified pool reserves. */
export function quoteBuySoby({ usdtInAtomic, usdtReserveAtomic, sobyReserveAtomic,
  feeBps = 100, minSobyOutAtomic = 0n }) {
  return quoteExactInput({
    amountIn: usdtInAtomic,
    reserveIn: usdtReserveAtomic,
    reserveOut: sobyReserveAtomic,
    feeBps,
    minAmountOut: minSobyOutAtomic
  });
}

/** SOBY (18 decimals) -> USDT (6 decimals), with verified pool reserves. */
export function quoteSellSoby({ sobyInAtomic, sobyReserveAtomic, usdtReserveAtomic,
  feeBps = 100, minUsdtOutAtomic = 0n }) {
  return quoteExactInput({
    amountIn: sobyInAtomic,
    reserveIn: sobyReserveAtomic,
    reserveOut: usdtReserveAtomic,
    feeBps,
    minAmountOut: minUsdtOutAtomic
  });
}
