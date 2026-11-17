import { getPaymentRates } from "./market-data.js";
import { verifyEvmPayment, verifySolPayment, verifyNativeSobyPayout } from "./payment-verification.js";
import { issueOwnerChallenge, consumeOwnerChallenge } from "./owner-auth.js";
import { calculateDynamicPrice } from "./pricing.js";

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
  const reservations = await db.prepare(`
    SELECT COALESCE(SUM(CAST(q.soby_amount_wei AS REAL) / 1000000000000000000), 0) AS reserved
    FROM quotes q LEFT JOIN orders o ON o.quote_id=q.id
    WHERE (q.status='issued' AND q.expires_at > ?) OR o.status IN ('verified','payout_pending')
  `).bind(now).first();
  const reservedInventorySoby = Number(reservations?.reserved || 0);
  const policy = await db.prepare("SELECT * FROM pricing_policy WHERE id=1").first();
  const policyReady = Boolean(policy && [policy.baseline_demand_24h,policy.inventory_weight,policy.demand_weight,policy.upward_smoothing,policy.downward_smoothing,policy.floor_price_usd].every(v => v !== null && v !== undefined));
  const priceUsd = Number(state.current_price_usd);
  if (!Number.isFinite(priceUsd) || priceUsd <= 0) throw new Error("invalid_price_state");
  return {
    priceUsd, currency: "USD", unit: "SOBY",
    referencePriceUsd: Number(state.reference_price_usd),
    availableInventorySoby: Number(state.available_inventory_soby),
    reservedInventorySoby,
    availableForQuoteSoby: Math.max(0, Number(state.available_inventory_soby) - reservedInventorySoby),
    initialInventorySoby: Number(state.initial_inventory_soby),
    verifiedDemand24hSoby: Number(demand?.demand_24h || 0),
    verifiedDemand7dSoby: Number(demand?.demand_7d || 0),
    verifiedPurchases24h: Number(demand?.purchases_24h || 0),
    dynamicPricingEnabled: policyReady,
    priceStatus: policyReady ? "demand_inventory_policy_active" : "awaiting_owner_approved_pricing_parameters",
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
    const amountSoby = Number(sobyWei) / 1e18;
    if (!Number.isFinite(amountSoby) || amountSoby <= 0 || amountSoby > snapshot.availableForQuoteSoby) {
      return json({ error: "insufficient_inventory" }, 409, origin);
    }

    const id = crypto.randomUUID();
    const now = Math.floor(Date.now() / 1000);
    const expiresAt = now + 600;
    const reservation = await env.DB.prepare(`
      INSERT INTO quotes (id,buyer_address,payer_address,soby_amount_wei,price_usd_micros,total_usd_micros,
        payment_asset,payment_chain_id,payment_amount_base_units,expires_at,status,created_at)
      SELECT ?,?,?,?,?,?,?,?,?,?,'issued',?
      WHERE (SELECT available_inventory_soby - COALESCE((
        SELECT SUM(CAST(q.soby_amount_wei AS REAL) / 1000000000000000000)
        FROM quotes q LEFT JOIN orders o ON o.quote_id=q.id
        WHERE (q.status='issued' AND q.expires_at > ?) OR o.status IN ('verified','payout_pending')
      ),0) FROM pricing_state WHERE id=1) >= ?
    `).bind(id, body.buyerAddress.toLowerCase(), payerAddress, sobyWei.toString(), Number(priceMicros),
      Number(totalUsdMicros), body.paymentAsset, asset.chainId, paymentBaseUnits.toString(), expiresAt, now,
      now, amountSoby).run();
    if (!reservation.meta?.changes) return json({ error: "insufficient_inventory" }, 409, origin);

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
  const quote = await env.DB.prepare("SELECT * FROM quotes WHERE id = ?").bind(body.quoteId).first();
  if (!quote || !quote.payer_address || quote.status !== "issued") {
    return json({ error: "quote_expired_or_unavailable" }, 409, origin);
  }
  const asset = ASSETS[quote.payment_asset];
  if (!asset) return json({ error: "unsupported_payment_asset" }, 400, origin);

  // Verify first; a transaction submitted before its confirmation threshold can
  // be checked again later without permanently consuming its transaction hash.
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
    if (!Number.isFinite(result.blockTimestamp) || result.blockTimestamp > Number(quote.expires_at)) {
      throw new Error("quote_expired_before_payment");
    }
    const orderId = crypto.randomUUID();
    const now = Math.floor(Date.now() / 1000);
    await env.DB.prepare(`
      INSERT INTO orders (id,quote_id,buyer_address,payment_chain_id,payment_tx_hash,
        payment_amount_base_units,payment_asset,status,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,'verified',?,?)
    `).bind(orderId, quote.id, quote.buyer_address, quote.payment_chain_id,
      body.paymentReference, quote.payment_amount_base_units, quote.payment_asset, now, now).run();
    const marked = await env.DB.prepare("UPDATE quotes SET status='paid' WHERE id=? AND status='issued'")
      .bind(quote.id).run();
    if (!marked.meta?.changes) return json({ error: "quote_already_consumed" }, 409, origin);
    await env.DB.prepare(
      "INSERT INTO audit_events (order_id,event_type,details_json,created_at) VALUES (?,?,?,?)"
    ).bind(orderId, "payment_verified", JSON.stringify({
      paymentReference: body.paymentReference, asset: quote.payment_asset,
      amountBaseUnits: result.amountBaseUnits, confirmations: result.confirmations ?? null,
    }), now).run();
    return json({ orderId, status: "verified", payment: result, nextStep: "owner_manual_review_required" }, 200, origin);
  } catch (error) {
    const reason = String(error?.message || "verification_failed");
    const status = reason === "payment_not_final" || reason === "rpc_unavailable" ? 202 : 422;
    return json({
      error: status === 202 ? "payment_confirmation_pending" : "payment_not_verified",
      reason,
      retryable: status === 202
    }, status, origin);
  }
}


async function adminHash(v) {
  const b=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v));
  return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("");
}
function adminEqual(a,b) {
  const x=new TextEncoder().encode(String(a)),y=new TextEncoder().encode(String(b));let d=x.length^y.length;
  for(let i=0;i<Math.max(x.length,y.length);i++)d|=(x[i]||0)^(y[i]||0);
  return d===0;
}
async function adminSession(req,env) {
  const t=(req.headers.get("Authorization")||"").replace(/^Bearer\s+/i,"");
  if(!/^[a-f0-9]{64}$/.test(t)||!env.DB)throw new Error("admin_session_required");
  const hash=await adminHash(t),r=await env.DB.prepare("SELECT expires_at FROM admin_sessions WHERE token_hash=?").bind(hash).first();
  const now=Math.floor(Date.now()/1000);
  if(!r||Number(r.expires_at)<=now){if(r)await env.DB.prepare("DELETE FROM admin_sessions WHERE token_hash=?").bind(hash).run();throw new Error("admin_session_expired");}
  return hash;
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
        ownerApproval: "wallet_signature_required",
        payoutVerification: "native_sobya_transfer_12_confirmations",
        message: "Owner-approved payout endpoints are installed; buyer checkout remains fail-closed pending frontend and end-to-end verification.",
      }, 200, allowed);
    }

    if (url.pathname === "/api/admin/challenge" && request.method === "POST") {
      if (!env.DB) return json({ error: "database_not_configured" }, 503, allowed);
      let body; try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, allowed); }
      try { return json(await issueOwnerChallenge(env.DB, body?.address, body?.action, body?.context), 200, allowed); }
      catch (error) { return json({ error: error?.message || "owner_challenge_failed" }, 403, allowed); }
    }

    if (url.pathname === "/api/admin/orders" && request.method === "POST") {
      if (!env.DB) return json({ error: "database_not_configured" }, 503, allowed);
      let body; try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, allowed); }
      try {
        await consumeOwnerChallenge(env.DB, body.auth, "orders:list", "verified-orders");
        const result = await env.DB.prepare(`
          SELECT o.id,o.status,o.payment_asset,o.payment_tx_hash,o.created_at,o.updated_at,
            q.buyer_address,q.soby_amount_wei,q.price_usd_micros,q.total_usd_micros
          FROM orders o JOIN quotes q ON q.id=o.quote_id
          WHERE o.status IN ('verified','payout_pending') ORDER BY o.created_at ASC LIMIT 100
        `).all();
        return json({ orders: result.results || [] }, 200, allowed);
      } catch (error) { return json({ error: error?.message || "owner_auth_failed" }, 403, allowed); }
    }

    if (url.pathname === "/api/admin/pricing-policy" && request.method === "POST") {
      if (!env.DB) return json({ error: "database_not_configured" }, 503, allowed);
      let body; try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, allowed); }
      try {
        await consumeOwnerChallenge(env.DB, body.auth, "pricing:update", JSON.stringify(body.policy || {}));
        const p = body.policy || {};
        const values = [p.baselineDemand24h,p.inventoryWeight,p.demandWeight,p.upwardSmoothing,p.downwardSmoothing,p.floorPriceUsd].map(Number);
        if (values.some(v => !Number.isFinite(v)) || values[0] < 0 || values[1] < 0 || values[2] < 0 ||
            values[3] <= 0 || values[3] > 1 || values[4] <= 0 || values[4] > 1 || values[5] <= 0) {
          return json({ error: "invalid_pricing_policy" }, 400, allowed);
        }
        const now = Math.floor(Date.now()/1000);
        await env.DB.prepare(`
          INSERT INTO pricing_policy (id,baseline_demand_24h,inventory_weight,demand_weight,
            upward_smoothing,downward_smoothing,floor_price_usd,updated_at)
          VALUES (1,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET baseline_demand_24h=excluded.baseline_demand_24h,
            inventory_weight=excluded.inventory_weight,demand_weight=excluded.demand_weight,
            upward_smoothing=excluded.upward_smoothing,downward_smoothing=excluded.downward_smoothing,
            floor_price_usd=excluded.floor_price_usd,updated_at=excluded.updated_at
        `).bind(...values,now).run();
        await env.DB.prepare(
          "INSERT INTO audit_events (order_id,event_type,details_json,created_at) VALUES (NULL,?,?,?)"
        ).bind("pricing_policy_updated",JSON.stringify(p),now).run();
        return json({ saved: true, policy: p },200,allowed);
      } catch(error) { return json({ error:error?.message || "pricing_policy_update_failed" },403,allowed); }
    }

    if (url.pathname === "/api/admin/payout" && request.method === "POST") {
      if (!env.DB) return json({ error: "database_not_configured" }, 503, allowed);
      let body; try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, allowed); }
      try {
        await consumeOwnerChallenge(env.DB, body.auth, "order:payout", body.orderId + "|" + body.payoutTxHash);
        if (typeof body.orderId !== "string" || typeof body.payoutTxHash !== "string") {
          return json({ error: "order_and_payout_reference_required" }, 400, allowed);
        }
        const order = await env.DB.prepare(`
          SELECT o.id,o.status,q.buyer_address,q.soby_amount_wei
          FROM orders o JOIN quotes q ON q.id=o.quote_id WHERE o.id=?
        `).bind(body.orderId).first();
        if (!order || order.status !== "verified") return json({ error: "order_not_awaiting_payout" }, 409, allowed);
        const payout = await verifyNativeSobyPayout({
          txHash: body.payoutTxHash,
          expectedAmount: order.soby_amount_wei,
          expectedBuyer: order.buyer_address
        });
        const now = Math.floor(Date.now() / 1000);
        const changed = await env.DB.prepare(
          "UPDATE orders SET status='paid',payout_tx_hash=?,updated_at=? WHERE id=? AND status='verified'"
        ).bind(body.payoutTxHash, now, order.id).run();
        if (!changed.meta?.changes) return json({ error: "order_already_processed" }, 409, allowed);
        const state = await env.DB.prepare("SELECT * FROM pricing_state WHERE id=1").first();
        const sold = await env.DB.prepare(`
          SELECT COALESCE(SUM(CAST(q.soby_amount_wei AS REAL)/1000000000000000000),0) AS total
          FROM orders o JOIN quotes q ON q.id=o.quote_id WHERE o.status='paid'
        `).first();
        const remaining = Math.max(0, Number(state.initial_inventory_soby) - Number(sold?.total || 0));
        const policy = await env.DB.prepare("SELECT * FROM pricing_policy WHERE id=1").first();
        const policyReady = Boolean(policy && [policy.baseline_demand_24h,policy.inventory_weight,policy.demand_weight,policy.upward_smoothing,policy.downward_smoothing,policy.floor_price_usd].every(v => v !== null && v !== undefined));
        let nextPrice = Number(state.current_price_usd);
        if (policyReady) {
          const demand = await env.DB.prepare(`
            SELECT COALESCE(SUM(CAST(q.soby_amount_wei AS REAL)/1000000000000000000),0) AS total
            FROM orders o JOIN quotes q ON q.id=o.quote_id
            WHERE o.status='paid' AND o.updated_at>=?
          `).bind(now - 86400).first();
          nextPrice = calculateDynamicPrice({
            referencePriceUsd: Number(state.reference_price_usd),
            previousPriceUsd: Number(state.current_price_usd),
            availableInventory: remaining,
            initialInventory: Number(state.initial_inventory_soby),
            verifiedDemand24h: Number(demand?.total || 0),
            baselineDemand24h: Number(policy.baseline_demand_24h),
            inventoryWeight: Number(policy.inventory_weight),
            demandWeight: Number(policy.demand_weight),
            upwardSmoothing: Number(policy.upward_smoothing),
            downwardSmoothing: Number(policy.downward_smoothing),
            floorPriceUsd: Number(policy.floor_price_usd)
          });
        }
        await env.DB.prepare(
          "UPDATE pricing_state SET available_inventory_soby=?,current_price_usd=?,updated_at=? WHERE id=1"
        ).bind(remaining, nextPrice, now).run();
        await env.DB.prepare(
          "INSERT INTO audit_events (order_id,event_type,details_json,created_at) VALUES (?,?,?,?)"
        ).bind(order.id, "soby_payout_confirmed", JSON.stringify(payout), now).run();
        return json({ orderId: order.id, status: "paid", payout }, 200, allowed);
      } catch (error) {
        return json({ error: error?.message || "payout_verification_failed" }, 422, allowed);
      }
    }



    if(url.pathname==="/api/admin/login"&&request.method==="POST"){
      if(!env.DB)return json({error:"database_not_configured"},503,allowed);
      if(!env.SOBYA_ADMIN_PASSWORD)return json({error:"admin_password_not_configured"},503,allowed);
      let b;try{b=await request.json();}catch{return json({error:"invalid_json"},400,allowed);}
      const ipHash=await adminHash(request.headers.get("CF-Connecting-IP")||"unknown"),now=Math.floor(Date.now()/1000);
      await env.DB.prepare("DELETE FROM admin_login_attempts WHERE attempted_at < ?").bind(now-900).run();
      const a=await env.DB.prepare("SELECT COUNT(*) AS total FROM admin_login_attempts WHERE ip_hash=? AND attempted_at>=?").bind(ipHash,now-900).first();
      if(Number(a?.total||0)>=5)return json({error:"login_rate_limited"},429,allowed);
      await env.DB.prepare("INSERT INTO admin_login_attempts(ip_hash,attempted_at) VALUES(?,?)").bind(ipHash,now).run();
      if(!adminEqual(typeof b?.password==="string"?b.password:"",env.SOBYA_ADMIN_PASSWORD))return json({error:"invalid_admin_password"},401,allowed);
      await env.DB.prepare("DELETE FROM admin_login_attempts WHERE ip_hash=?").bind(ipHash).run();
      const bytes=new Uint8Array(32);crypto.getRandomValues(bytes);
      const token=[...bytes].map(x=>x.toString(16).padStart(2,"0")).join(""),hash=await adminHash(token),expires=now+28800;
      await env.DB.prepare("INSERT INTO admin_sessions(token_hash,expires_at,created_at) VALUES(?,?,?)").bind(hash,expires,now).run();
      return json({token,expiresAt:expires},200,allowed);
    }
    if(url.pathname==="/api/admin/logout"&&request.method==="POST"){
      try{const hash=await adminSession(request,env);await env.DB.prepare("DELETE FROM admin_sessions WHERE token_hash=?").bind(hash).run();return json({loggedOut:true},200,allowed);}
      catch(e){return json({error:e?.message||"admin_session_required"},401,allowed);}
    }

    // Manual-only SOBYA BUY: buyers submit details; the owner verifies payment and sends SOBY offline.
    if (url.pathname === "/api/manual/price" && request.method === "GET") {
      if (!env.DB) return json({error:"database_not_configured"},503,allowed);
      const row = await env.DB.prepare("SELECT price_usd FROM manual_sale_settings WHERE id=1").first();
      return json({priceUsd:Number(row?.price_usd || 0.005),currency:"USD",mode:"manual"},200,allowed);
    }
    if (url.pathname === "/api/manual/orders" && request.method === "POST") {
      if (!env.DB) return json({error:"database_not_configured"},503,allowed);
      let b; try { b=await request.json(); } catch { return json({error:"invalid_json"},400,allowed); }
      const amount=String(b?.sobyAmount ?? "");
      const network=String(b?.paymentNetwork ?? "").trim();
      const asset=String(b?.paymentAsset ?? "").trim();
      const paid=String(b?.paymentAmount ?? "").trim();
      const tx=String(b?.paymentTx ?? "").trim();
      const buyer=String(b?.buyerAddress ?? "").trim();
      if (!/^\\d+(?:\\.\\d{1,18})?$/.test(amount) || Number(amount)<=0 || Number(amount)>1000000000 ||
          !network || network.length>80 || !asset || asset.length>40 || !paid || paid.length>80 ||
          !tx || tx.length>180 || !/^0x[0-9a-fA-F]{40}$/.test(buyer)) {
        return json({error:"invalid_order_details"},400,allowed);
      }
      const settings=await env.DB.prepare("SELECT price_usd FROM manual_sale_settings WHERE id=1").first();
      const price=Number(settings?.price_usd || 0.005);
      const total=Number((Number(amount)*price).toFixed(8));
      const id=crypto.randomUUID();
      const now=Math.floor(Date.now()/1000);
      await env.DB.prepare("INSERT INTO manual_orders (id,soby_amount,unit_price_usd,total_usd,payment_network,payment_asset,payment_amount,payment_tx,buyer_address,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,'submitted',?,?)")
        .bind(id,amount,price,total,network,asset,paid,tx,buyer.toLowerCase(),now,now).run();
      return json({orderId:id,status:"submitted",unitPriceUsd:price,totalUsd:total},201,allowed);
    }
    if (url.pathname === "/api/admin/manual/orders" && request.method === "POST") {
      if (!env.DB) return json({error:"database_not_configured"},503,allowed);
      let b; try { b=await request.json(); } catch { return json({error:"invalid_json"},400,allowed); }
      try {
        await adminSession(request,env);
        const result=await env.DB.prepare("SELECT * FROM manual_orders ORDER BY created_at DESC LIMIT 200").all();
        return json({orders:result.results||[]},200,allowed);
      } catch(e) { return json({error:e?.message||"owner_auth_failed"},403,allowed); }
    }
    if (url.pathname === "/api/admin/manual/price" && request.method === "POST") {
      if (!env.DB) return json({error:"database_not_configured"},503,allowed);
      let b; try { b=await request.json(); } catch { return json({error:"invalid_json"},400,allowed); }
      try {
        const price=Number(b.priceUsd);
        await adminSession(request,env);
        if (!Number.isFinite(price)||price<=0||price>1000000) return json({error:"invalid_price"},400,allowed);
        await env.DB.prepare("UPDATE manual_sale_settings SET price_usd=?,updated_at=? WHERE id=1").bind(price,Math.floor(Date.now()/1000)).run();
        return json({saved:true,priceUsd:price},200,allowed);
      } catch(e) { return json({error:e?.message||"price_update_failed"},403,allowed); }
    }
    if (url.pathname === "/api/admin/manual/order-status" && request.method === "POST") {
      if (!env.DB) return json({error:"database_not_configured"},503,allowed);
      let b; try { b=await request.json(); } catch { return json({error:"invalid_json"},400,allowed); }
      try {
        await adminSession(request,env);
        if (!["under_review","paid_confirmed","completed","rejected"].includes(b.status)) return json({error:"invalid_status"},400,allowed);
        await env.DB.prepare("UPDATE manual_orders SET status=?,payout_tx=?,updated_at=? WHERE id=?")
          .bind(b.status,String(b.payoutTx||"").slice(0,180),Math.floor(Date.now()/1000),String(b.orderId)).run();
        return json({saved:true},200,allowed);
      } catch(e) { return json({error:e?.message||"order_update_failed"},403,allowed); }
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
