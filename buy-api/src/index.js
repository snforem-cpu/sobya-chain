import { getPaymentRates } from "./market-data.js";
import { verifyEvmPayment, verifySolPayment } from "./payment-verification.js";

const json = (body, status = 200, origin = "*") => new Response(JSON.stringify(body), {
  status, headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization",
    "vary": "Origin",
  },
});

export function validAddress(value) {
  return typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value);
}

const ASSETS = Object.freeze({
  ETH: { verifier: "ETH_ETHEREUM", rate: "ETH", chainId: 1, decimals: 18 },
  USDT_ETH: { verifier: "USDT_ETHEREUM", rate: "USDT", chainId: 1, decimals: 6 },
  BNB: { verifier: "BNB_BSC", rate: "BNB", chainId: 56, decimals: 18 },
  SOL_SOLANA: { verifier: "SOL_SOLANA", rate: "SOL", chainId: 0, decimals: 9 },
});

function decimalToScaled(value, scale) {
  if (typeof value !== "string" || !/^\d+(?:\.\d+)?$/.test(value)) throw new Error("invalid_amount");
  const [whole, fraction = ""] = value.split(".");
  if (fraction.length > scale) throw new Error("too_many_decimals");
  return BigInt(whole) * (10n ** BigInt(scale)) + BigInt((fraction + "0".repeat(scale)).slice(0, scale) || "0");
}

function formatScaled(value, scale) {
  const digits = value.toString().padStart(scale + 1, "0");
  const whole = digits.slice(0, -scale);
  const fraction = digits.slice(-scale).replace(/0+$/, "");
  return fraction ? whole + "." + fraction : whole;
}

function rateToMicros(value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) throw new Error("invalid_market_rate");
  return BigInt(Math.round(value * 1_000_000));
}

async function getPriceSnapshot(db) {
  const state = await db.prepare(
    "SELECT reference_price_usd, current_price_usd, initial_inventory_soby, available_inventory_soby, updated_at FROM pricing_state WHERE id = 1"
  ).first();
  if (!state) throw new Error("pricing_state_missing");
  const now = Math.floor(Date.now() / 1000);
  const demand = await db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN o.updated_at >= ? THEN CAST(q.soby_amount_wei AS REAL) / 1000000000000000000 ELSE 0 END), 0) AS demand_24h,
      COALESCE(SUM(CASE WHEN o.updated_at >= ? THEN CAST(q.soby_amount_wei AS REAL) / 1000000000000000000 ELSE 0 END), 0) AS demand_7d,
      COALESCE(SUM(CASE WHEN o.updated_at >= ? THEN 1 ELSE 0 END), 0) AS purchases_24h
    FROM orders o INNER JOIN quotes q ON q.id = o.quote_id
    WHERE o.status = 'paid' AND o.updated_at >= ?
  `).bind(now - 86400, now - 604800, now - 86400, now - 604800).first();
  const priceUsd = Number(state.current_price_usd);
  if (!Number.isFinite(priceUsd) || priceUsd <= 0) throw new Error("invalid_price_state");
  return {
    priceUsd, currency: "USD", unit: "SOBY",
    referencePriceUsd: Number(state.reference_price_usd),
    availableInventorySoby: Number(state.available_inventory_soby),
    initialInventorySoby: Number(state.initial_inventory_soby),
    verifiedDemand24hSoby: Number(demand?.demand_24h || 0),
    verifiedDemand7dSoby: Number(demand?.demand_7d || 0),
    verifiedPurchases24h: Number(demand?.purchases_24h || 0),
    dynamicPricingEnabled: false,
    priceStatus: "stored_price_waiting_for_purchase_engine",
    updatedAt: Number(state.updated_at),
  };
}

async function createQuote(request, env, origin) {
  if (!env.DB) return json({ error: "database_not_configured" }, 503, origin);
  let body;
  try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, origin); }
  if (!validAddress(body?.buyerAddress)) return json({ error: "invalid_buyer_address" }, 400, origin);
  const asset = ASSETS[body?.paymentAsset];
  if (!asset) return json({ error: "unsupported_payment_asset" }, 400, origin);
  const payerAddress = body?.paymentSenderAddress || body?.buyerAddress;
  const validSolanaAddress = value => typeof value === "string" && /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(value);
  if (body.paymentAsset === "SOL_SOLANA" ? !validSolanaAddress(payerAddress) : !validAddress(payerAddress)) {
    return json({ error: "invalid_payment_sender_address" }, 400, origin);
  }

  try {
    const sobyWei = decimalToScaled(String(body.sobyAmount ?? ""), 18);
    if (sobyWei <= 0n || sobyWei > 1_000_000n * 10n ** 18n) throw new Error("invalid_amount");
    const [snapshot, market] = await Promise.all([getPriceSnapshot(env.DB), getPaymentRates()]);
    const priceMicros = BigInt(Math.round(snapshot.priceUsd * 1_000_000));
    const totalUsdMicros = (sobyWei * priceMicros + 10n ** 18n - 1n) / (10n ** 18n);
    const paymentRateMicros = rateToMicros(market.rates[asset.rate]);
    const numerator = totalUsdMicros * (10n ** BigInt(asset.decimals));
    const paymentBaseUnits = (numerator + paymentRateMicros - 1n) / paymentRateMicros;
    if (paymentBaseUnits <= 0n) throw new Error("invalid_payment_quote");
    if (Number(body.sobyAmount) > snapshot.availableInventorySoby) return json({ error: "insufficient_inventory" }, 409, origin);

    const id = crypto.randomUUID();
    const now = Math.floor(Date.now() / 1000);
    const expiresAt = now + 600;
    await env.DB.prepare(`
      INSERT INTO quotes (id,buyer_address,payer_address,soby_amount_wei,price_usd_micros,total_usd_micros,
        payment_asset,payment_chain_id,payment_amount_base_units,expires_at,status,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,'issued',?)
    `).bind(id, body.buyerAddress.toLowerCase(), payerAddress, sobyWei.toString(), Number(priceMicros),
      Number(totalUsdMicros), body.paymentAsset, asset.chainId, paymentBaseUnits.toString(), expiresAt, now).run();

    return json({
      quoteId: id,
      buyerAddress: body.buyerAddress,
      sobyAmount: String(body.sobyAmount),
      unitPriceUsd: snapshot.priceUsd,
      totalUsd: Number(totalUsdMicros) / 1_000_000,
      paymentAsset: body.paymentAsset,
      paymentAmount: formatScaled(paymentBaseUnits, asset.decimals),
      paymentAmountBaseUnits: paymentBaseUnits.toString(),
      paymentRecipient: body.paymentAsset === "SOL_SOLANA"
        ? "ACTkwKD9ZhHYgRSEoM7QWvp5ig1cUxDo3gMzB55rocdk"
        : "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
      expiresAt,
      marketFetchedAt: market.fetchedAt,
    }, 201, origin);
  } catch (error) {
    const code = ["invalid_amount","too_many_decimals","invalid_market_rate","invalid_payment_quote"].includes(error?.message)
      ? error.message : "quote_unavailable";
    return json({ error: code, message: "A verified quote could not be created. Do not send funds." }, 503, origin);
  }
}

async function verifyOrder(request, env, origin) {
  if (!env.DB) return json({ error: "database_not_configured" }, 503, origin);
  let body;
  try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, origin); }
  if (typeof body?.quoteId !== "string" || typeof body?.paymentReference !== "string") {
    return json({ error: "quote_and_payment_reference_required" }, 400, origin);
  }
  const quote = await env.DB.prepare(
    "SELECT * FROM quotes WHERE id = ?"
  ).bind(body.quoteId).first();
  if (!quote || !quote.payer_address || quote.status !== "issued" || quote.expires_at < Math.floor(Date.now() / 1000)) {
    return json({ error: "quote_expired_or_unavailable" }, 409, origin);
  }
  const asset = ASSETS[quote.payment_asset];
  if (!asset) return json({ error: "unsupported_payment_asset" }, 400, origin);

  const orderId = crypto.randomUUID();
  const now = Math.floor(Date.now() / 1000);
  try {
    await env.DB.prepare(`
      INSERT INTO orders (id,quote_id,buyer_address,payment_chain_id,payment_tx_hash,
        payment_amount_base_units,payment_asset,status,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,'confirming',?,?)
    `).bind(orderId, quote.id, quote.buyer_address, quote.payment_chain_id,
      body.paymentReference, quote.payment_amount_base_units, quote.payment_asset, now, now).run();
  } catch (_) {
    return json({ error: "payment_reference_already_used" }, 409, origin);
  }

  try {
    const result = quote.payment_asset === "SOL_SOLANA"
      ? await verifySolPayment({
          signature: body.paymentReference,
          expectedAmount: quote.payment_amount_base_units,
          expectedSender: quote.payer_address,
        })
      : await verifyEvmPayment({
          asset: asset.verifier,
          txHash: body.paymentReference,
          expectedAmount: quote.payment_amount_base_units,
          expectedSender: quote.payer_address,
        });
    await env.DB.prepare("UPDATE orders SET status='verified', updated_at=? WHERE id=?")
      .bind(Math.floor(Date.now() / 1000), orderId).run();
    await env.DB.prepare("UPDATE quotes SET status='paid' WHERE id=?").bind(quote.id).run();
    await env.DB.prepare(
      "INSERT INTO audit_events (order_id,event_type,details_json,created_at) VALUES (?,?,?,?)"
    ).bind(orderId, "payment_verified", JSON.stringify({
      paymentReference: body.paymentReference, asset: quote.payment_asset,
      amountBaseUnits: result.amountBaseUnits, confirmations: result.confirmations ?? null,
    }), Math.floor(Date.now() / 1000)).run();
    return json({ orderId, status: "verified", payment: result, nextStep: "owner_manual_review_required" }, 200, origin);
  } catch (error) {
    await env.DB.prepare("UPDATE orders SET status='failed', failure_code=?, updated_at=? WHERE id=?")
      .bind(String(error?.message || "verification_failed").slice(0, 80), Math.floor(Date.now() / 1000), orderId).run();
    return json({ error: "payment_not_verified", reason: String(error?.message || "verification_failed") }, 422, origin);
  }
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
        service: "sobya-buy-api", status: "online",
        databaseConfigured: Boolean(env.DB),
        salesEnabled: env.SALE_ENABLED === "true",
        commerceReady: false,
        message: "Manual owner-approved SOBY payout is not enabled; do not treat verified payment as a completed purchase.",
      }, 200, allowed);
    }

    if (url.pathname === "/api/payment-rates" && request.method === "GET") {
      try { return json(await getPaymentRates(), 200, allowed); }
      catch { return json({ error: "market_data_unavailable", message: "Rates unavailable. Do not send funds." }, 503, allowed); }
    }

    if (url.pathname === "/api/price" && request.method === "GET") {
      if (!env.DB) return json({ error: "database_not_configured" }, 503, allowed);
      try { return json(await getPriceSnapshot(env.DB), 200, allowed); }
      catch (error) {
        return json({ error: "price_unavailable", message: error?.message === "pricing_state_missing"
          ? "Apply the SOBYA BUY pricing database migrations first." : "The live price is temporarily unavailable." }, 503, allowed);
      }
    }

    if (env.SALE_ENABLED === "true" && url.pathname === "/api/quote" && request.method === "POST") {
      return createQuote(request, env, allowed);
    }
    if (env.SALE_ENABLED === "true" && url.pathname === "/api/orders/verify-payment" && request.method === "POST") {
      return verifyOrder(request, env, allowed);
    }

    if (url.pathname.startsWith("/api/")) {
      return json({ error: "commerce_not_configured", message: "SOBYA BUY is not accepting payments yet. Do not send funds." }, 503, allowed);
    }
    return json({ error: "not_found" }, 404, allowed);
  },
};

export { getPriceSnapshot };
