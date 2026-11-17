import test from "node:test";
import assert from "node:assert/strict";
import worker, { getPriceSnapshot } from "../src/index.js";

function fakeDb({ state, demand = {} }) {
  const seen = [];
  return {
    seen,
    prepare(sql) {
      seen.push(sql);
      return {
        bind() { return this; },
        async first() {
          if (sql.includes("FROM pricing_state")) return state;
          if (sql.includes("FROM quotes q LEFT JOIN orders o")) return { reserved: 0 };
          if (sql.includes("FROM pricing_policy")) return null;
          if (sql.includes("FROM orders o")) return {
            demand_24h: 0,
            demand_7d: 0,
            purchases_24h: 0,
            ...demand,
          };
          throw new Error("Unexpected SQL in test: " + sql);
        },
      };
    },
  };
}

const state = {
  reference_price_usd: 0.005,
  current_price_usd: 0.005,
  initial_inventory_soby: 1_000_000,
  available_inventory_soby: 1_000_000,
  updated_at: 1_800_000_000,
};

test("price snapshot keeps the persisted opening price; rolling demand is telemetry only", async () => {
  const db = fakeDb({ state, demand: { demand_24h: 12, demand_7d: 40, purchases_24h: 3 } });
  const result = await getPriceSnapshot(db);
  assert.equal(result.priceUsd, 0.005);
  assert.equal(result.dynamicPricingEnabled, false);
  assert.equal(result.priceStatus, "awaiting_owner_approved_pricing_parameters");
  assert.equal(result.verifiedDemand24hSoby, 12);
  assert.equal(result.verifiedDemand7dSoby, 40);
  assert.equal(result.verifiedPurchases24h, 3);
  assert.equal(db.seen.length, 4);
  assert.ok(db.seen[1].includes("WHERE o.status = 'paid'"));
  assert.equal(result.reservedInventorySoby, 0);
  assert.equal(result.availableForQuoteSoby, 1_000_000);
});

test("elapsed time and changes in rolling demand never alter the stored price", async () => {
  const lowDemandDb = fakeDb({ state: { ...state, current_price_usd: 0.0125 }, demand: { demand_24h: 0, demand_7d: 8 } });
  const highDemandDb = fakeDb({ state: { ...state, current_price_usd: 0.0125 }, demand: { demand_24h: 500_000, demand_7d: 900_000 } });
  const lowDemand = await getPriceSnapshot(lowDemandDb);
  const highDemand = await getPriceSnapshot(highDemandDb);
  assert.equal(lowDemand.priceUsd, 0.0125);
  assert.equal(highDemand.priceUsd, 0.0125);
  assert.equal(lowDemand.dynamicPricingEnabled, false);
  assert.equal(highDemand.dynamicPricingEnabled, false);
});

test("missing pricing state fails rather than fabricating a price", async () => {
  const db = fakeDb({ state: null });
  await assert.rejects(() => getPriceSnapshot(db), /pricing_state_missing/);
});

test("price endpoint refuses to report a live price without D1 binding", async () => {
  const response = await worker.fetch(
    new Request("https://example.workers.dev/api/price"),
    { ALLOWED_ORIGIN: "https://snforem-cpu.github.io" },
  );
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.error, "database_not_configured");
});
