import test from "node:test";
import assert from "node:assert/strict";
import worker, { getPriceSnapshot } from "../src/index.js";

function fakeDb({ state, policy = null, demand = {} }) {
  const seen = [];
  return {
    seen,
    prepare(sql) {
      seen.push(sql);
      return {
        bind() { return this; },
        async first() {
          if (sql.includes("FROM pricing_state")) return state;
          if (sql.includes("FROM pricing_policy")) return policy;
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

test("price snapshot reports opening reference until production policy is configured", async () => {
  const db = fakeDb({ state, policy: null, demand: { demand_24h: 12, demand_7d: 40, purchases_24h: 3 } });
  const result = await getPriceSnapshot(db);
  assert.equal(result.priceUsd, 0.005);
  assert.equal(result.dynamicPricingEnabled, false);
  assert.equal(result.priceStatus, "opening_price_policy_pending");
  assert.equal(result.verifiedDemand24hSoby, 12);
  assert.equal(result.verifiedDemand7dSoby, 40);
  assert.equal(result.verifiedPurchases24h, 3);
  assert.match(db.seen[2], /o\.status = 'paid'/);
});

test("complete policy calculates an uncapped price from verified demand", async () => {
  const policy = {
    baseline_demand_24h: 100,
    inventory_weight: 0.25,
    demand_weight: 0.1,
    upward_smoothing: 0.5,
    downward_smoothing: 0.1,
    floor_price_usd: 0.0025,
  };
  const db = fakeDb({
    state: { ...state, current_price_usd: 100 },
    policy,
    demand: { demand_24h: 100_000, demand_7d: 100_000, purchases_24h: 25 },
  });
  const result = await getPriceSnapshot(db);
  assert.equal(result.dynamicPricingEnabled, true);
  assert.ok(result.priceUsd > 100);
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
