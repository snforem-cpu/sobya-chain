import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../worker.js";

const env = { SOBYA_RPC_URL: "https://sobya-evm-rpc.nodesafe-dapp.xyz" };

test("health endpoint describes the read-only SOBYA Mainnet API", async () => {
  const res = await worker.fetch(new Request("https://api.example/v1/health"), env);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.service, "SOBYA Verify API");
  assert.equal(body.chainId, "357812033857");
  assert.equal(body.readOnly, true);
});

test("unknown route returns JSON 404", async () => {
  const res = await worker.fetch(new Request("https://api.example/nope"), env);
  assert.equal(res.status, 404);
  assert.equal((await res.json()).ok, false);
});

test("malformed JSON returns JSON 400", async () => {
  const res = await worker.fetch(new Request("https://api.example/v1/verify/proof", {
    method: "POST", headers: { "content-type": "application/json" }, body: "{"
  }), env);
  assert.equal(res.status, 400);
});

test("invoice endpoint rejects missing file hash before RPC", async () => {
  const res = await worker.fetch(new Request("https://api.example/v1/verify/invoice", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ txHash: "0x" + "1".repeat(64), metadata: {} })
  }), env);
  assert.equal(res.status, 422);
  assert.match((await res.json()).error.message, /fileHash/);
});

test("oversized request is rejected", async () => {
  const res = await worker.fetch(new Request("https://api.example/v1/verify/proof", {
    method: "POST", body: " ".repeat(17000)
  }), env);
  assert.equal(res.status, 413);
});

test("live SOBYA transaction is verified by the HTTP handler", async () => {
  const txHash = "0x615604f8649ffd4f407e64e2eb14eb91a84720fd63d0dc4eaa17088647ed4206";
  const fileHash = "0x6d21ebc214b9104c6ec30538bd78036327fa86acba1aeebd303eb5badf7ffbb4";
  const res = await worker.fetch(new Request("https://api.example/v1/verify/proof", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ txHash, fileHash })
  }), env);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.result.valid, true);
  assert.equal(body.result.match, true);
  assert.equal(body.result.txHash, txHash);
});
