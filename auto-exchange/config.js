// SOBYA Auto Exchange — isolated policy configuration.
// This module is intentionally read-only and does not enable transfers.
export const AUTO_EXCHANGE_POLICY = Object.freeze({
  quoteCurrency: "USDT",
  payoutAsset: "SOBY",
  openingPriceUsdtPerSoby: "0.005",
  referenceInventorySoby: 1_000_000,
  exchangeFeeBps: 100,
  upwardPriceCoefficient: 100,
  downwardPriceCoefficient: 25,
  priceImpactDenominator: 10_000,
  quoteValiditySeconds: 600,
  maxPrice: null,
  timeOnlyPriceChanges: false,
  priceChangesRequireConfirmedTrades: true,
  // Public EVM address supplied by the project owner. The same 20-byte
  // address is used on Ethereum (USDT inventory destination) and SOBYA EVM
  // (SOBY payout source); balances and transactions remain chain-specific.
  inventoryWalletEvmAddress: "0xebdb899fFE84a89e1d576964b640491c135651AD",
  ethereumChainId: 1,
  sobyaEvmChainId: 357812033857,
  tradingEnabled: false,
  payoutEnabled: false,
});

// Directional asymmetry is fixed at 4:1; coefficients are basis points
// applied proportionally to trade size relative to reference inventory.
export function getDirectionalPriceCoefficient(direction) {
  if (direction === "up") return AUTO_EXCHANGE_POLICY.upwardPriceCoefficient;
  if (direction === "down") return AUTO_EXCHANGE_POLICY.downwardPriceCoefficient;
  throw new TypeError('direction must be "up" or "down"');
}
