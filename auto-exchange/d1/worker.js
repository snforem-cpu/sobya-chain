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
  return (n / 10n**BigInt(decimals)).toString() + "." +
    (n % 10n**BigInt(decimals)).toString().padStart(decimals,"0").replace(/0+$/,"");
}
function validAddress(value) { return /^0x[0-9a-fA-F]{40}$/.test(String(value || "")); }
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
  const sender = body.sender.toLowerCase();
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
    if (!origin) return response({error:"Origin not allowed"},403,ORIGIN);
    if (url.pathname === "/v1/quote" && request.method === "POST") {
      try { return await createQuote(request,env); }
      catch (error) { return response({error:String(error.message || error)},400,origin); }
    }
    if (url.pathname === "/v1/price" && request.method === "GET") {
      const row = await env.DB.prepare("SELECT current_price_usdt_per_soby FROM exchange_state WHERE id=1").first();
      return response({price:row?.current_price_usdt_per_soby || "0.005",quoteValiditySeconds:QUOTE_TTL_SECONDS,feeBps:FEE_BPS},200,origin);
    }
    if (url.pathname === "/internal/open-quotes" && request.method === "GET") {
      const auth = request.headers.get("Authorization") || "";
      if (!env.D1_SYNC_TOKEN || auth !== "Bearer " + env.D1_SYNC_TOKEN)
        return response({error:"Unauthorized"},401,ORIGIN);
      const result = await env.DB.prepare("SELECT * FROM exchange_quotes WHERE status IN ('open','paid','returned','refund_waiting_funds') ORDER BY created_at").all();
      return response({quotes:result.results || []},200,ORIGIN);
    }
    return response({error:"Not found"},404,origin || ORIGIN);
  }
};
