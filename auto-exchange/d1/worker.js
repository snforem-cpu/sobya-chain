const ORIGIN = "https://snforem-cpu.github.io";
const INVENTORY = "0xebdb899fFE84a89e1d576964b640491c135651AD".toLowerCase();
const USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7".toLowerCase();
const ETHEREUM_CHAIN_ID = 1;
const SOBYA_CHAIN_ID = 357812033857;
const FEE_BPS = 100;
const QUOTE_TTL_SECONDS = 600;
const USDT_SCALE = 10n ** 6n;
const SOBY_SCALE = 10n ** 18n;
const PRICE_SCALE = 10n ** 18n;

function response(data, status = 200, origin = ORIGIN) {
  return new Response(JSON.stringify(data), { status, headers: {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization",
    "vary": "Origin"
  }});
}
function corsOrigin(request) {
  const origin = request.headers.get("Origin");
  return origin === ORIGIN ? ORIGIN : null;
}
function parseUnits(value, decimals) {
  const s = String(value ?? "").trim();
  const re = decimals === 6 ? /^\d+(?:\.\d{1,6})?$/ : /^\d+(?:\.\d{1,18})?$/;
  if (!re.test(s)) throw new Error("Invalid amount precision");
  const [whole, fraction = ""] = s.split(".");
  const n = BigInt(whole) * 10n ** BigInt(decimals) +
    BigInt((fraction + "0".repeat(decimals)).slice(0, decimals));
  if (n <= 0n) throw new Error("Amount must be greater than zero");
  return n;
}
function priceAtomic(value) {
  const s = String(value);
  if (!/^\d+(?:\.\d{1,18})?$/.test(s)) throw new Error("Invalid exchange price");
  const [whole, fraction = ""] = s.split(".");
  const n = BigInt(whole) * PRICE_SCALE + BigInt((fraction + "0".repeat(18)).slice(0,18));
  if (n <= 0n) throw new Error("Invalid exchange price");
  return n;
}
function formatAtomic(n, decimals) {
  const fraction = (n % 10n**BigInt(decimals)).toString().padStart(decimals,"0").replace(/0+$/,"");
  return (n / 10n**BigInt(decimals)).toString() + (fraction ? "." + fraction : "");
}
function validAddress(value) { return /^0x[0-9a-fA-F]{40}$/.test(String(value || "")); }
function decodeBase64Url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  return Uint8Array.from(atob(padded), c => c.charCodeAt(0));
}
async function verifyGitHubOidc(token) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) return false;
  let header, claims;
  try {
    header = JSON.parse(new TextDecoder().decode(decodeBase64Url(parts[0])));
    claims = JSON.parse(new TextDecoder().decode(decodeBase64Url(parts[1])));
  } catch { return false; }
  const now = Math.floor(Date.now() / 1000);
  if (header.alg !== "RS256" || !header.kid ||
      claims.iss !== "https://token.actions.githubusercontent.com" ||
      claims.aud !== "sobya-auto-exchange" ||
      claims.repository !== "snforem-cpu/sobya-chain" ||
      claims.ref !== "refs/heads/main" ||
      !Number.isFinite(claims.exp) || claims.exp <= now ||
      (Number.isFinite(claims.nbf) && claims.nbf > now + 30) ||
      (Number.isFinite(claims.iat) && claims.iat > now + 30)) return false;
  const allowed = new Set([
    "snforem-cpu/sobya-chain/.github/workflows/auto-exchange-payout.yml@refs/heads/main",
    "snforem-cpu/sobya-chain/.github/workflows/auto-exchange-return-refund.yml@refs/heads/main"
  ]);
  if (!allowed.has(claims.workflow_ref)) return false;
  const jwksResponse = await fetch("https://token.actions.githubusercontent.com/.well-known/jwks");
  if (!jwksResponse.ok) return false;
  const jwks = await jwksResponse.json();
  const jwk = (jwks.keys || []).find(key => key.kid === header.kid && key.kty === "RSA");
  if (!jwk) return false;
  try {
    const publicKey = await crypto.subtle.importKey("jwk", jwk,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const signed = new TextEncoder().encode(parts[0] + "." + parts[1]);
    return await crypto.subtle.verify("RSASSA-PKCS1-v1_5", publicKey, decodeBase64Url(parts[2]), signed);
  } catch { return false; }
}
function quoteForLedger(row) {
  const base = {
    orderId: row.order_id, sender: row.sender, depositAddress: row.deposit_address,
    chainId: Number(row.chain_id), requestedAmountAtomic: row.requested_amount_atomic,
    paymentAmountAtomic: row.payment_amount_atomic, payoutAmountAtomic: row.payout_amount_atomic,
    quotedPrice: row.quoted_price, exchangeFeeBps: Number(row.exchange_fee_bps),
    createdAt: row.created_at, expiresAt: row.expires_at, status: row.status
  };
  if (row.direction === "buy") return { ...base, tokenAddress: row.token_address,
    depositTxHash: row.payment_tx_hash || undefined, payoutTxHash: row.settlement_tx_hash || undefined };
  return { ...base, returnTxHash: row.payment_tx_hash || undefined,
    refundTxHash: row.settlement_tx_hash || undefined };
}
async function createQuote(request, env) {
  const body = await request.json();
  const direction = body.direction;
  if (!["buy","return"].includes(direction)) return response({error:"Invalid exchange direction"},400);
  if (!validAddress(body.sender)) return response({error:"Connect a valid EVM wallet first"},400);
  const decimals = direction === "buy" ? 6 : 18;
  const requested = parseUnits(body.amount, decimals);
  const state = await env.DB.prepare("SELECT current_price_usdt_per_soby FROM exchange_state WHERE id=1").first();
  if (!state) throw new Error("Exchange price state is not initialized");
  const price = priceAtomic(state.current_price_usdt_per_soby);
  const now = new Date();
  const createdAt = now.toISOString();
  const expiresAt = new Date(now.getTime() + QUOTE_TTL_SECONDS*1000).toISOString();
  await env.DB.prepare("UPDATE exchange_quotes SET status = 'expired', updated_at = ?1 WHERE status = 'open' AND expires_at <= ?1").bind(createdAt).run();
  const sender = body.sender.toLowerCase();
  const recent = await env.DB.prepare("SELECT COUNT(*) AS total FROM exchange_quotes WHERE sender=?1 AND direction=?2 AND status='open' AND created_at>=?3")
    .bind(sender,direction,new Date(now.getTime()-60_000).toISOString()).first();
  if (Number(recent?.total || 0) >= 3)
    return response({error:"Too many active quote requests. Please wait before requesting another quote."},429);
  const active = await env.DB.prepare("SELECT COUNT(*) AS total FROM exchange_quotes WHERE sender=?1 AND direction=?2 AND status='open'")
    .bind(sender,direction).first();
  if (Number(active?.total || 0) >= 3)
    return response({error:"You already have three active quotes in this direction. Complete or let one expire first."},429);
  const orderId = "SOBYA-" + crypto.randomUUID().replaceAll("-","").toUpperCase();
  for (let marker=1n; marker<=1000n; marker++) {
    const payment = requested + marker;
    const payout = direction === "buy"
      ? payment * SOBY_SCALE * (10000n-BigInt(FEE_BPS)) * PRICE_SCALE / (USDT_SCALE*price*10000n)
      : payment * price * USDT_SCALE * BigInt(10000-FEE_BPS) / (SOBY_SCALE*PRICE_SCALE*10000n);
    if (payout <= 0n) return response({error:"Amount is too small for a positive settlement"},400);
    const row = {
      order_id: orderId, direction, sender,
      deposit_address: INVENTORY,
      token_address: direction === "buy" ? USDT : null,
      chain_id: direction === "buy" ? ETHEREUM_CHAIN_ID : SOBYA_CHAIN_ID,
      requested_amount_atomic: requested.toString(),
      payment_amount_atomic: payment.toString(),
      unique_marker_atomic: marker.toString(),
      payout_amount_atomic: payout.toString(),
      quoted_price: state.current_price_usdt_per_soby,
      exchange_fee_bps: FEE_BPS, created_at: createdAt, expires_at: expiresAt,
      status: "open", updated_at: createdAt
    };
    try {
      await env.DB.prepare(`INSERT INTO exchange_quotes
        (order_id,direction,sender,deposit_address,token_address,chain_id,requested_amount_atomic,
         payment_amount_atomic,unique_marker_atomic,payout_amount_atomic,quoted_price,exchange_fee_bps,
         created_at,expires_at,status,updated_at)
        VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,'open',?13)`)
        .bind(row.order_id,row.direction,row.sender,row.deposit_address,row.token_address,row.chain_id,
          row.requested_amount_atomic,row.payment_amount_atomic,row.unique_marker_atomic,row.payout_amount_atomic,
          row.quoted_price,row.exchange_fee_bps,row.created_at,row.expires_at).run();
      return response({
        orderId, direction, sender,
        paymentAmount: formatAtomic(payment,decimals),
        paymentAmountAtomic: payment.toString(),
        payoutAmount: formatAtomic(payout,direction === "buy" ? 18 : 6),
        payoutAmountAtomic: payout.toString(),
        quotedPrice: row.quoted_price, exchangeFeeBps:FEE_BPS,
        chainId:row.chain_id, depositAddress:INVENTORY, tokenAddress:row.token_address,
        createdAt, expiresAt, validForSeconds:QUOTE_TTL_SECONDS
      });
    } catch (error) {
      if (!String(error).includes("UNIQUE")) throw error;
    }
  }
  return response({error:"Could not reserve a unique payment amount. Please request a new quote."},409);
}
export default {
  async fetch(request, env) {
    const origin = corsOrigin(request);
    if (request.method === "OPTIONS") {
      if (!origin) return new Response(null,{status:403});
      return new Response(null,{status:204,headers:{
        "access-control-allow-origin":origin,
        "access-control-allow-methods":"GET,POST,OPTIONS",
        "access-control-allow-headers":"content-type,authorization",
        "access-control-max-age":"86400","vary":"Origin"
      }});
    }
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return response({service:"SOBYA Auto Exchange API",status:"ok"},200,origin || ORIGIN);
    }
    if (url.pathname === "/internal/open-quotes" && request.method === "GET") {
      const auth = request.headers.get("Authorization") || "";
      if (!(await verifyGitHubOidc(auth.startsWith("Bearer ") ? auth.slice(7) : "")))
        return response({error:"Unauthorized"},401,ORIGIN);
      const result = await env.DB.prepare("SELECT * FROM exchange_quotes WHERE status IN ('open','paid','returned','refund_waiting_funds','payout_waiting_funds','settled','refunded','review') ORDER BY created_at").all();
      return response({quotes:(result.results || []).map(quoteForLedger)},200,ORIGIN);
    }
    if (url.pathname === "/internal/sync-ledger" && request.method === "POST") {
      const auth = request.headers.get("Authorization") || "";
      if (!(await verifyGitHubOidc(auth.startsWith("Bearer ") ? auth.slice(7) : "")))
        return response({error:"Unauthorized"},401,ORIGIN);
      const body = await request.json();
      const updates = Array.isArray(body.quotes) ? body.quotes : [];
      const returns = Array.isArray(body.returnQuotes) ? body.returnQuotes : [];
      const statements = [];
      const allowedStatuses = new Set(["open","paid","returned","review","payout_waiting_funds","payout_prepared","payout_broadcast","settled","expired","refund_waiting_funds","refund_prepared","refund_broadcast","refunded"]);
      for (const q of [...updates.map(q => ({...q,direction:"buy"})), ...returns.map(q => ({...q,direction:"return"}))]) {
        if (typeof q.orderId !== "string" || !["buy","return"].includes(q.direction) ||
            !allowedStatuses.has(q.status)) continue;
        statements.push(env.DB.prepare("UPDATE exchange_quotes SET status=?1,payment_tx_hash=?2,settlement_tx_hash=?3,last_error=?4,updated_at=?5 WHERE order_id=?6 AND direction=?7")
          .bind(q.status, q.depositTxHash || q.returnTxHash || null, q.payoutTxHash || q.refundTxHash || null,
            q.payoutReviewReason || q.refundWaitReason || q.payoutWaitReason || null,
            new Date().toISOString(), q.orderId, q.direction));
      }
      if (body.currentPriceUsdtPerSoby !== undefined) {
        const price = String(body.currentPriceUsdtPerSoby);
        if (!/^\\d+(?:\\.\\d{1,18})?$/.test(price) || /^0(?:\\.0*)?$/.test(price))
          return response({error:"Invalid current exchange price"},400,ORIGIN);
        statements.push(env.DB.prepare("UPDATE exchange_state SET current_price_usdt_per_soby=?1,updated_at=?2 WHERE id=1")
          .bind(price,new Date().toISOString()));
      }
      if (statements.length) await env.DB.batch(statements);
      return response({updated:statements.length},200,ORIGIN);
    }
    if (!origin) return response({error:"Origin not allowed"},403,ORIGIN);
    if (url.pathname.startsWith("/v1/order/") && request.method === "GET") {
      const orderId = decodeURIComponent(url.pathname.slice("/v1/order/".length));
      if (!/^SOBYA-[A-F0-9-]{20,80}$/.test(orderId))
        return response({error:"Invalid order ID"},400,origin);
      const row = await env.DB.prepare("SELECT order_id,direction,status,created_at,expires_at,payment_tx_hash,settlement_tx_hash,last_error FROM exchange_quotes WHERE order_id=?1")
        .bind(orderId).first();
      if (!row) return response({error:"Order not found"},404,origin);
      return response({orderId:row.order_id,direction:row.direction,status:row.status,
        createdAt:row.created_at,expiresAt:row.expires_at,
        paymentTxHash:row.payment_tx_hash || null,settlementTxHash:row.settlement_tx_hash || null,
        message:row.status === "settled" || row.status === "refunded" ? "Exchange completed" :
          row.status === "review" ? "Order requires review" : "Payment received or awaiting confirmation"},200,origin);
    }
    if (url.pathname === "/v1/quote" && request.method === "POST") {
      try { return await createQuote(request,env); }
      catch (error) { return response({error:String(error.message || error)},400,origin); }
    }
    if (url.pathname === "/v1/price" && request.method === "GET") {
      const row = await env.DB.prepare("SELECT current_price_usdt_per_soby FROM exchange_state WHERE id=1").first();
      return response({price:row?.current_price_usdt_per_soby || "0.005",quoteValiditySeconds:QUOTE_TTL_SECONDS,feeBps:FEE_BPS},200,origin);
    }
    return response({error:"Not found"},404,origin || ORIGIN);
  }
};
