import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import worker from "../src/index.js";

test("manual BUY configuration preserves SOBYA network identity without fixed payment rails", async () => {
  const source = await readFile(new URL("../../buy/config.js", import.meta.url), "utf8");
  const context = { window: {} };
  vm.runInNewContext(source, context);
  const config = context.window.SOBYA_BUY_CONFIG;
  assert.equal(config.paymentsEnabled, false);
  assert.equal(config.sobyaChainId, 357812033857);
  assert.equal(config.sobyaRpcUrl, "https://sobya-evm-rpc.nodesafe-dapp.xyz");
  assert.equal(config.sobyaExplorerUrl, "https://explorer.nodesafe-app.xyz/sobya");
  assert.equal(config.salePriceUsd, 0.005);
  assert.equal("paymentReceivingAddresses" in config, false);
  assert.equal("assets" in config, false);
});

test("health endpoint never reports commerce ready while sales are disabled", async () => {
  const response = await worker.fetch(
    new Request("https://example.workers.dev/health"),
    { ALLOWED_ORIGIN: "https://snforem-cpu.github.io", SALE_ENABLED: "false" },
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.salesEnabled, false);
  assert.equal(body.commerceReady, false);
});

test("all commerce API routes remain fail-closed", async () => {
  for (const path of ["/api/quote", "/api/orders", "/api/payments/verify", "/api/owner/challenge", "/api/owner/orders", "/api/payout/confirm"]) {
    const response = await worker.fetch(
      new Request("https://example.workers.dev" + path, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" }),
      { ALLOWED_ORIGIN: "https://snforem-cpu.github.io", SALE_ENABLED: "false" },
    );
    assert.equal(response.status, 503, path);
    const body = await response.json();
    assert.equal(body.error, "commerce_not_configured", path);
  }
});
