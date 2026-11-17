import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import worker from "../src/index.js";

test("public payment destinations match owner-confirmed addresses and stay distinct from inventory", async () => {
  const source = await readFile(new URL("../../buy/config.js", import.meta.url), "utf8");
  const context = { window: {} };
  vm.runInNewContext(source, context);
  const config = context.window.SOBYA_BUY_CONFIG;
  assert.equal(config.paymentReceivingAddresses.ETH_ETHEREUM, "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f");
  assert.equal(config.paymentReceivingAddresses.USDT_ETHEREUM, "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f");
  assert.equal(config.paymentReceivingAddresses.BNB_BSC, "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f");
  assert.equal(config.paymentReceivingAddresses.SOL_SOLANA, "ACTkwKD9ZhHYgRSEoM7QWvp5ig1cUxDo3gMzB55rocdk");
  assert.equal(config.inventoryWalletAddress, "0xebdb899fFE84a89e1d576964b640491c135651AD");
  assert.notEqual(config.inventoryWalletAddress, config.paymentReceivingAddresses.ETH_ETHEREUM);
  assert.equal(config.paymentsEnabled, false);
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
