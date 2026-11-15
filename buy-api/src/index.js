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

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = env.ALLOWED_ORIGIN || "";
    if (request.method === "OPTIONS") {
      if (origin !== allowed) return json({ error: "origin_not_allowed" }, 403, allowed);
      return json({}, 204, allowed);
    }
    if (origin && origin !== allowed) return json({ error: "origin_not_allowed" }, 403, allowed);

    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return json({
        service: "sobya-buy-api",
        status: "online",
        salesEnabled: env.SALE_ENABLED === "true",
        commerceReady: false,
        message: "Payment verification and payout are not enabled.",
      }, 200, allowed);
    }

    // Fail closed until RPC/oracle verification, signing, D1 provisioning,
    // operational limits and end-to-end tests are configured.
    if (url.pathname.startsWith("/api/")) {
      return json({
        error: "commerce_not_configured",
        message: "SOBYA BUY is not accepting payments yet. Do not send funds.",
      }, 503, allowed);
    }
    return json({ error: "not_found" }, 404, allowed);
  },
};

export { validAddress };
