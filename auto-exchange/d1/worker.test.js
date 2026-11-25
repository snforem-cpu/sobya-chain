import test from "node:test";
import assert from "node:assert/strict";
import worker from "./worker.js";

function database() {
  const rows = [];
  return {
    rows,
    prepare(sql) {
      let args = [];
      const statement = {
        bind(...values) { args = values; return statement; },
        async first() {
          if (sql.includes("exchange_state")) return { current_price_usdt_per_soby: "0.005" };
          if (sql.includes("COUNT(*)")) return { total: 0 };
          return null;
        },
        async run() { rows.push({ sql, args }); return { success: true }; },
        async all() { return { results: [] }; }
      };
      return statement;
    },
    async batch(statements) { return Promise.all(statements.map(s => s.run())); }
  };
}
async function call(path, { method = "GET", body, origin = "https://snforem-cpu.github.io", env } = {}) {
  const request = new Request("https://sobya-buy-api.snforem.workers.dev" + path, {
    method, headers: { Origin: origin, ...(body ? { "content-type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
  return worker.fetch(request, env || { DB: database() });
}

test("health endpoint returns online without exposing internals", async () => {
  const response = await call("/health");
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { service: "SOBYA Auto Exchange API", status: "ok" });
});

test("price endpoint returns configured opening price", async () => {
  const response = await call("/v1/price", { env: { DB: database() } });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.price, "0.005");
  assert.equal(body.feeBps, 100);
  assert.equal(body.quoteValiditySeconds, 600);
});

test("buy quote reserves exact unique USDT amount and calculates net SOBY", async () => {
  const DB = database();
  const response = await call("/v1/quote", {
    method: "POST", env: { DB },
    body: { direction: "buy", sender: "0x1111111111111111111111111111111111111111", amount: "10" }
  });
  assert.equal(response.status, 200);
  const quote = await response.json();
  assert.equal(quote.paymentAmount, "10.000001");
  assert.equal(quote.payoutAmount, "1980.000198");
  assert.equal(quote.chainId, 1);
  assert.equal(quote.depositAddress.toLowerCase(), "0xebdb899ff e84a89e1d576964b640491c135651ad".replaceAll(" ",""));
  assert.equal(DB.rows.filter(row => row.sql.includes("INSERT INTO exchange_quotes")).length, 1);
});

test("return quote reserves exact unique SOBY amount and calculates net USDT", async () => {
  const DB = database();
  const response = await call("/v1/quote", {
    method: "POST", env: { DB },
    body: { direction: "return", sender: "0x1111111111111111111111111111111111111111", amount: "1000" }
  });
  assert.equal(response.status, 200);
  const quote = await response.json();
  assert.equal(quote.paymentAmount, "1000.000000000000000001");
  assert.equal(quote.payoutAmount, "4.950000");
  assert.equal(quote.chainId, 357812033857);
  assert.equal(quote.tokenAddress, null);
});

test("rejects invalid origins and malformed quote requests", async () => {
  const badOrigin = await call("/v1/price", { origin: "https://evil.example", env: { DB: database() } });
  assert.equal(badOrigin.status, 403);
  const badAmount = await call("/v1/quote", { method: "POST", env: { DB: database() },
    body: { direction: "buy", sender: "0x1111111111111111111111111111111111111111", amount: "1.0000001" } });
  assert.equal(badAmount.status, 400);
});

test("internal D1 endpoints reject requests without a valid GitHub OIDC token", async () => {
  const read = await call("/internal/open-quotes", { env: { DB: database() } });
  assert.equal(read.status, 401);
  const write = await call("/internal/sync-ledger", { method: "POST", env: { DB: database() },
    body: { quotes: [], returnQuotes: [] } });
  assert.equal(write.status, 401);
});
