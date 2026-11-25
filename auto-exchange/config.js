// SOBYA Auto Exchange — isolated policy configuration.
// This module is intentionally read-only and does not enable transfers.
export const AUTO_EXCHANGE_POLICY = Object.freeze({
  quoteCurrency: "USDT",
  payoutAsset: "SOBY",
  openingPriceUsdtPerSoby: 0.005,
  referenceInventorySoby: 1_000_000,
  exchangeFeeBps: 100,
  upwardPriceCoefficient: 1000,
  downwardPriceCoefficient: 250,
  quoteValiditySeconds: 600,
  maxPrice: null,
  timeOnlyPriceChanges: false,
  priceChangesRequireConfirmedTrades: true,
  tradingEnabled: false,
  payoutEnabled: false,
});

// Directional asymmetry is fixed at 4:1. The absolute impact unit/normalizer
// has deliberately not been guessed; it must be specified before live quotes.
export function getDirectionalPriceCoefficient(direction) {
  if (direction === "up") return AUTO_EXCHANGE_POLICY.upwardPriceCoefficient;
  if (direction === "down") return AUTO_EXCHANGE_POLICY.downwardPriceCoefficient;
  throw new TypeError('direction must be "up" or "down"');
}
