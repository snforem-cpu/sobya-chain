// SOBYA Auto Exchange — isolated policy configuration.
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
  // Same EVM address on Ethereum and SOBYA; balances are chain-specific.
  inventoryWalletEvmAddress: "0xebdb899fFE84a89e1d576964b640491c135651AD",
  ethereumChainId: 1,
  sobyaEvmChainId: 357812033857,
  // Activate the funded USDT -> SOBY purchase direction only.
  buyTradingEnabled: true,
  buyPayoutEnabled: true,
  // Keep SOBY -> USDT returns closed until USDT and Ethereum gas reserves exist.
  returnTradingEnabled: false,
  returnRefundEnabled: false,
});

export function getDirectionalPriceCoefficient(direction) {
  if (direction === "up") return AUTO_EXCHANGE_POLICY.upwardPriceCoefficient;
  if (direction === "down") return AUTO_EXCHANGE_POLICY.downwardPriceCoefficient;
  throw new TypeError('direction must be "up" or "down"');
}
