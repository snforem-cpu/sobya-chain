const COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price";

const ASSET_IDS = Object.freeze({
  ETH: "ethereum",
  BNB: "binancecoin",
  SOL: "solana",
  USDT: "tether",
});

export async function getPaymentRates(fetchImpl = fetch, now = Date.now()) {
  const ids = Object.values(ASSET_IDS).join(",");
  const url = new URL(COINGECKO_URL);
  url.searchParams.set("ids", ids);
  url.searchParams.set("vs_currencies", "usd");
  const response = await fetchImpl(url, {
    headers: { accept: "application/json" },
    cf: { cacheTtl: 20, cacheEverything: true },
  });
  if (!response.ok) throw new Error("market_data_unavailable");
  const data = await response.json();
  const rates = {};
  for (const [symbol, id] of Object.entries(ASSET_IDS)) {
    const value = Number(data?.[id]?.usd);
    if (!Number.isFinite(value) || value <= 0) throw new Error("invalid_market_rate");
    rates[symbol] = value;
  }
  return {
    currency: "USD",
    source: "CoinGecko",
    fetchedAt: Math.floor(now / 1000),
    maxAgeSeconds: 60,
    rates,
  };
}
