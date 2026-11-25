
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
        salesEnabled: false,
        commerceReady: false,
        message: "Manual purchase-request service only. Payments are reviewed and SOBY is sent manually by the owner.",
      }, 200, allowed);
    }

    if (url.pathname === "/api/admin/license-reservations" && request.method === "POST") {
      if (!env.DB) return json({ error: "database_not_configured" }, 503, allowed);
      try {
        await adminSession(request, env);
        let body; try { body = await request.json(); } catch { return json({ error: "invalid_json" }, 400, allowed); }
        const tx = String(body?.transactionHash || "").toLowerCase();
        const licenseId = String(body?.licenseId || "").trim();
        if (!/^0x[0-9a-f]{64}$/.test(tx) || !/^[A-Za-z0-9_-]{1,80}$/.test(licenseId)) {
          return json({ error: "invalid_reservation" }, 400, allowed);
        }
        const now = Math.floor(Date.now() / 1000);
        try {
          await env.DB.prepare(
            "INSERT INTO license_issuance_reservations (transaction_hash, license_id, created_at) VALUES (?, ?, ?)"
          ).bind(tx, licenseId, now).run();
        } catch (error) {
          const existing = await env.DB.prepare(
            "SELECT transaction_hash, license_id FROM license_issuance_reservations WHERE transaction_hash=? OR license_id=? LIMIT 1"
          ).bind(tx, licenseId).first();
          if (existing) return json({ error: "transaction_or_license_already_reserved" }, 409, allowed);
          throw error;
        }
        return json({ reserved: true, transactionHash: tx, licenseId, createdAt: now }, 201, allowed);
      } catch (error) {
        const status = error?.message === "admin_session_required" || error?.message === "admin_session_expired" ? 401 : 503;
        return json({ error: error?.message || "reservation_failed" }, status, allowed);
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
      const amount=String(b?.sobyAmount ?? "").trim();
      const network=String(b?.paymentNetwork ?? "").trim();
      const asset=String(b?.paymentAsset ?? "").trim();
      const paid=String(b?.paymentAmount ?? "").trim();
      const tx=String(b?.paymentTx ?? "").trim();
      const buyer=String(b?.buyerAddress ?? "").trim();
      // Preserve the original multi-network, multi-asset manual request workflow.
      if (!/^\d+(?:\.\d{1,18})?$/.test(amount) || Number(amount)<=0 || Number(amount)>1000000000 ||
          !network || !asset || !paid || !tx || !validAddress(buyer)) {
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

    if (url.pathname.startsWith("/api/")) {
      return json({ error: "commerce_not_configured", message: "SOBYA BUY is not accepting payments yet. Do not send funds." }, 503, allowed);
    }
    return json({ error: "not_found" }, 404, allowed);
  },
};

