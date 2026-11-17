import test from "node:test";
import assert from "node:assert/strict";
import { getPaymentRates } from "../src/market-data.js";

test("returns live USD rates for all accepted payment assets", async () => {
  let requested;
  const result = await getPaymentRates(async (url, options) => {
    requested = { url: String(url), options };
    return new Response(JSON.stringify({
      ethereum: { usd: 3200 },
      binancecoin: { usd: 900 },
      solana: { usd: 150 },
      tether: { usd: 1.001 },
    }), { status: 200, headers: { "content-type": "application/json" } });
  }, 1_800_000_000_000);

  assert.deepEqual(result.rates, { ETH: 3200, BNB: 900, SOL: 150, USDT: 1.001 });
  assert.equal(result.source, "CoinGecko");
  assert.equal(result.fetchedAt, 1_800_000_000);
  assert.match(requested.url, /ethereum%2Cbinancecoin%2Csolana%2Ctether/);
});

test("fails closed when the market data provider is unavailable", async () => {
  await assert.rejects(
    getPaymentRates(async () => new Response("rate limited", { status: 429 })),
    /market_data_unavailable/,
  );
});

test("rejects incomplete or invalid market rates", async () => {
  await assert.rejects(
    getPaymentRates(async () => new Response(JSON.stringify({
      ethereum: { usd: 3200 }, binancecoin: { usd: 900 }, solana: { usd: 150 },
    }), { status: 200 })),
    /invalid_market_rate/,
  );
});
