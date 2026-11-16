import { calculateDynamicPrice } from "./pricing.js";

const json = (body, status = 200, origin = "*") => new Response(JSON.stringify(body), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization",
    "vary": "Origin",
  },
});

function validAddress(value) {
  return typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value);
}

async function getPriceSnapshot(db) {
  const state = await db.prepare(
    "SELECT reference_price_usd, current_price_usd, initial_inventory_soby, available_inventory_soby, updated_at FROM pricing_state WHERE id = 1"
  ).first();
  if (!state) throw new Error("pricing_state_missing");

  const policy = await db.prepare(
    "SELECT baseline_demand_24h, inventory_weight, demand_weight, upward_smoothing, downward_smoothing, floor_price_usd FROM pricing_policy WHERE id = 1"
  ).first();

  // Only orders whose full payout lifecycle is complete count as purchases.
  // Pending, confirming, verified-but-not-paid, failed and refunded orders
  // are deliberately excluded from demand.
  const now = Math.floor(Date.now() / 1000);
  const demand = await db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN o.updated_at >= ? THEN CAST(q.soby_amount_wei AS REAL) / 1000000000000000000 ELSE 0 END), 0) AS demand_24h,
      COALESCE(SUM(CASE WHEN o.updated_at >= ? THEN CAST(q.soby_amount_wei AS REAL) / 1000000000000000000 ELSE 0 END), 0) AS demand_7d,
      COALESCE(SUM(CASE WHEN o.updated_at >= ? THEN 1 ELSE 0 END), 0) AS purchases_24h
    FROM orders o
    INNER JOIN quotes q ON q.id = o.quote_id
    WHERE o.status = 'paid' AND o.updated_at >= ?
  `).bind(now - 86400, now - 604800, now - 86400, now - 604800).first();

  const completePolicy = policy && [
    policy.baseline_demand_24h, policy.inventory_weight, policy.demand_weight,
    policy.upward_smoothing, policy.downward_smoothing, policy.floor_price_usd,
  ].every(value => value !== null && value !== undefined && Number.isFinite(Number(value)));

  let priceUsd = Number(state.current_price_usd);
  let dynamicPricingEnabled = false;
  if (completePolicy) {
    priceUsd = calculateDynamicPrice({
      referencePriceUsd: Number(state.reference_price_usd),
      previousPriceUsd: Number(state.current_price_usd),
      availableInventory: Number(state.available_inventory_soby),
      initialInventory: Number(state.initial_inventory_soby),
      verifiedDemand24h: Number(demand?.demand_24h || 0),
      baselineDemand24h: Number(policy.baseline_demand_24h),
      inventoryWeight: Number(policy.inventory_weight),
      demandWeight: Number(policy.demand_weight),
      upwardSmoothing: Number(policy.upward_smoothing),
      downwardSmoothing: Number(policy.downward_smoothing),
      floorPriceUsd: Number(policy.floor_price_usd),
    });
    dynamicPricingEnabled = true;
  }

  if (!Number.isFinite(priceUsd) || priceUsd <= 0) throw new Error("invalid_price_state");
  return {
    priceUsd,
    currency: "USD",
    unit: "SOBY",
    referencePriceUsd: Number(state.reference_price_usd),
    availableInventorySoby: Number(state.available_inventory_soby),
    initialInventorySoby: Number(state.initial_inventory_soby),
    verifiedDemand24hSoby: Number(demand?.demand_24h || 0),
    verifiedDemand7dSoby: Number(demand?.demand_7d || 0),
    verifiedPurchases24h: Number(demand?.purchases_24h || 0),
    dynamicPricingEnabled,
    priceStatus: dynamicPricingEnabled ? "live_calculated" : "opening_price_policy_pending",
    updatedAt: Number(state.updated_at),
  };
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = env.ALLOWED_ORIGIN || "";
    if (request.method === "OPTIONS") {
      if (origin !== allowed) return json({ error: "origin_not_allowed" }, 403, allowed);
      return new Response(null, { status: 204, headers: {
        "access-control-allow-origin": allowed,
        "access-control-allow-methods": "GET,POST,OPTIONS",
        "access-control-allow-headers": "content-type,authorization",
        "vary": "Origin",
      }});
    }
    if (origin && origin !== allowed) return json({ error: "origin_not_allowed" }, 403, allowed);

    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return json({
        service: "sobya-buy-api",
        status: "online",
        databaseConfigured: Boolean(env.DB),
        salesEnabled: env.SALE_ENABLED === "true",
        commerceReady: false,
        message: "Payment verification and payout are not enabled.",
      }, 200, allowed);
    }

    if (url.pathname === "/api/price" && request.method === "GET") {
      if (!env.DB) return json({
        error: "database_not_configured",
        message: "The SOBYA BUY D1 database binding is not configured.",
      }, 503, allowed);
      try {
        return json(await getPriceSnapshot(env.DB), 200, allowed);
      } catch (error) {
        // Do not expose database details or substitute a fabricated live price.
        return json({
          error: "price_unavailable",
          message: error?.message === "pricing_state_missing"
            ? "Apply the SOBYA BUY pricing database migrations first."
            : "The live price is temporarily unavailable.",
        }, 503, allowed);
      }
    }

    // Fail closed until payment verification, payout signing, operational
    // limits and end-to-end tests are configured.
    if (url.pathname.startsWith("/api/")) {
      return json({
        error: "commerce_not_configured",
        message: "SOBYA BUY is not accepting payments yet. Do not send funds.",
      }, 503, allowed);
    }
    return json({ error: "not_found" }, 404, allowed);
  },
};

export { validAddress, getPriceSnapshot };
