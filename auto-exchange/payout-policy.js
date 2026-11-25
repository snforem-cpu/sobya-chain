// Pure native-balance policy for a SOBY payout and its network fee reserve.
export function calculateRequiredPayoutBalance({ payoutAmountAtomic, gasLimit, maxFeePerGas, gasBufferBps = 2_000 }) {
  const payout = BigInt(payoutAmountAtomic);
  const gas = BigInt(gasLimit);
  const fee = BigInt(maxFeePerGas);
  if (payout <= 0n || gas <= 0n || fee < 0n) {
    throw new TypeError("payout amount and gas limit must be positive; fee cannot be negative");
  }
  if (!Number.isSafeInteger(gasBufferBps) || gasBufferBps < 0 || gasBufferBps > 10_000) {
    throw new TypeError("gasBufferBps must be an integer from 0 to 10000");
  }
  const bufferedGas = (gas * fee * BigInt(10_000 + gasBufferBps) + 9_999n) / 10_000n;
  return payout + bufferedGas;
}


// A payout is eligible only before a nonce reservation or transaction hash exists.
// Prepared/broadcast orders are intentionally held for reconciliation, never retried blindly.
export function isPayoutEligible(quote) {
  return (quote?.status === "paid" || quote?.status === "payout_waiting_funds") &&
    quote.payoutTxHash === undefined && quote.payoutNonce === undefined;
}
