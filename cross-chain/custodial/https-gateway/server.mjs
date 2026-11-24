import http from "node:http";
import https from "node:https";
import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

const PORT = Number(process.env.PORT || 25701);
const UPSTREAM = process.env.SOBYA_UPSTREAM_URL || "";
const ALLOWED_ORIGIN = process.env.SOBYA_ALLOWED_ORIGIN || "https://snforem-cpu.github.io";
const GATEWAY_TOKEN = process.env.SOBYA_GATEWAY_TOKEN || "";
const MAX_BODY = 16384;
const WINDOW_MS = 60000;
const MAX_REQUESTS = 60;
const buckets = new Map();

function configuredUpstream() {
  let url;
  try { url = new URL(UPSTREAM); } catch { throw new Error("SOBYA_UPSTREAM_URL must be set to the Enzonic Connect origin"); }
  if (!["http:", "https:"].includes(url.protocol) ||
      url.hostname !== "fr-one.enzonic.com" || url.port !== "25701" ||
      url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("Upstream must be the configured Enzonic Connect host and primary port");
  }
  return url;
}

function allowedPath(path) {
  return path === "/health" || path === "/v1/quotes" ||
    /^\/v1\/orders\/[0-9a-f-]{36}$/.test(path) ||
    /^\/v1\/orders\/[0-9a-f-]{36}\/deposit$/.test(path);
}

function rateLimit(req, res) {
  const ip = req.socket.remoteAddress || "unknown";
  const now = Date.now();
  const current = buckets.get(ip) || { start: now, count: 0 };
  if (now - current.start >= WINDOW_MS) { current.start = now; current.count = 0; }
  current.count += 1;
  buckets.set(ip, current);
  if (buckets.size > 5000) {
    for (const [key, value] of buckets) if (now - value.start >= WINDOW_MS) buckets.delete(key);
  }
  if (current.count > MAX_REQUESTS) {
    res.writeHead(429, { "Content-Type": "application/json", "Cache-Control": "no-store", "Retry-After": "60" });
    res.end(JSON.stringify({ error: "rate limit exceeded" }));
    return false;
  }
  return true;
}

const server = http.createServer(async (req, res) => {
  let target;
  if (!GATEWAY_TOKEN) {
    res.writeHead(503, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    res.end(JSON.stringify({ error: "gateway authentication secret is not configured" }));
    return;
  }
  try { target = configuredUpstream(); }
  catch (error) {
    res.writeHead(503, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    res.end(JSON.stringify({ error: error.message }));
    return;
  }
  const path = new URL(req.url, "http://gateway.local").pathname;
  if (!allowedPath(path) || !["GET", "POST", "OPTIONS"].includes(req.method)) {
    res.writeHead(404, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    res.end(JSON.stringify({ error: "not found" }));
    return;
  }
  const origin = req.headers.origin;
  if (origin && origin !== ALLOWED_ORIGIN) {
    res.writeHead(403, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    res.end(JSON.stringify({ error: "origin is not allowed" }));
    return;
  }
  if (!rateLimit(req, res)) return;

  let body = Buffer.alloc(0);
  try {
    for await (const chunk of req) {
      body = Buffer.concat([body, chunk]);
      if (body.length > MAX_BODY) {
        res.writeHead(413, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        res.end(JSON.stringify({ error: "request body too large" }));
        return;
      }
    }
  } catch {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "could not read request body" }));
    return;
  }

  const transport = target.protocol === "https:" ? https : http;
  const headers = {
    "Accept": "application/json",
    "Cache-Control": "no-store",
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Host": req.headers.host || "",
    "Content-Length": String(body.length)
  };
  if (req.headers["content-type"]) headers["Content-Type"] = req.headers["content-type"];
  if (origin) headers["Origin"] = origin;
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = randomBytes(16).toString("hex");
  const bodyHash = createHash("sha256").update(body).digest("hex");
  const requestCanonical = [timestamp, nonce, req.method, req.url, bodyHash].join("\n");
  const requestSignature = createHmac("sha256", GATEWAY_TOKEN).update(requestCanonical).digest("hex");
  headers["X-SOBYA-Request-Timestamp"] = timestamp;
  headers["X-SOBYA-Request-Nonce"] = nonce;
  headers["X-SOBYA-Request-Signature"] = requestSignature;

  const upstreamReq = transport.request({
    protocol: target.protocol, hostname: target.hostname, port: target.port,
    method: req.method, path: req.url, headers, timeout: 25000
  }, upstreamRes => {
    const chunks = [];
    upstreamRes.on("data", chunk => chunks.push(chunk));
    upstreamRes.on("end", () => {
      const responseBody = Buffer.concat(chunks);
      const responseTimestamp = String(upstreamRes.headers["x-sobya-response-timestamp"] || "");
      const responseNonce = String(upstreamRes.headers["x-sobya-response-nonce"] || "");
      const responseSignature = String(upstreamRes.headers["x-sobya-response-signature"] || "");
      const responseStatus = String(upstreamRes.statusCode || 502);
      const validTimestamp = /^\d+$/.test(responseTimestamp) && Math.abs(Math.floor(Date.now() / 1000) - Number(responseTimestamp)) <= 60;
      const responseCanonical = [responseTimestamp, nonce, responseStatus, createHash("sha256").update(responseBody).digest("hex")].join("\n");
      const expectedSignature = createHmac("sha256", GATEWAY_TOKEN).update(responseCanonical).digest();
      const suppliedSignature = /^[0-9a-f]{64}$/.test(responseSignature) ? Buffer.from(responseSignature, "hex") : Buffer.alloc(0);
      const authenticated = validTimestamp && responseNonce === nonce && suppliedSignature.length === expectedSignature.length && timingSafeEqual(suppliedSignature, expectedSignature);
      if (!authenticated) {
        res.writeHead(502, { "Content-Type": "application/json", "Cache-Control": "no-store" });
        res.end(JSON.stringify({ error: "upstream response authentication failed" }));
        return;
      }
      res.writeHead(Number(responseStatus), {
        "Content-Type": upstreamRes.headers["content-type"] || "application/json",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        ...(upstreamRes.headers["access-control-allow-origin"] ? { "Access-Control-Allow-Origin": upstreamRes.headers["access-control-allow-origin"], "Vary": "Origin" } : {}),
        ...(upstreamRes.headers["access-control-allow-methods"] ? { "Access-Control-Allow-Methods": upstreamRes.headers["access-control-allow-methods"], "Access-Control-Allow-Headers": upstreamRes.headers["access-control-allow-headers"] || "Content-Type" } : {})
      });
      res.end(responseBody);
    });
  });
  upstreamReq.on("timeout", () => upstreamReq.destroy(new Error("upstream timeout")));
  upstreamReq.on("error", () => {
    if (!res.headersSent) {
      res.writeHead(502, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(JSON.stringify({ error: "Enzonic Connect API upstream is unavailable" }));
    } else res.destroy();
  });
  if (body.length) upstreamReq.write(body);
  upstreamReq.end();
});

server.listen(PORT, "0.0.0.0", () => {
  console.log("SOBYA HTTPS gateway backend listening on port " + PORT);
});
