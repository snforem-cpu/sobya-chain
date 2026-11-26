import { readFile } from "node:fs/promises";

const apiBase = process.env.SOBYA_AUTO_EXCHANGE_API_URL || "https://sobya-buy-api.snforem.workers.dev";
const oidc = process.env.GITHUB_OIDC_TOKEN;
const repository = process.env.GH_REPOSITORY;
const token = process.env.GH_TOKEN;
if (!oidc || !repository || !token) throw new Error("GitHub OIDC token, repository, and GitHub token are required");
const api = "https://api.github.com/repos/" + repository;
const ghHeaders = { accept: "application/vnd.github+json", authorization: "Bearer " + token,
  "x-github-api-version": "2022-11-28" };
async function gh(path, options = {}) {
  const response = await fetch(api + path, { ...options,
    headers: { ...ghHeaders, ...(options.body ? { "content-type": "application/json" } : {}) } });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error("GitHub API " + response.status + ": " + JSON.stringify(body));
  return body;
}
async function d1(path, options = {}) {
  const response = await fetch(apiBase + path, { ...options,
    headers: { authorization: "Bearer " + oidc, ...(options.body ? { "content-type": "application/json" } : {}) } });
  const body = await response.json();
  if (!response.ok) throw new Error("SOBYA D1 API " + response.status + ": " + JSON.stringify(body));
  return body;
}
const ledgerFile = await gh("/contents/auto-exchange/ledger.json?ref=main");
const ledger = JSON.parse(Buffer.from(ledgerFile.content, "base64").toString("utf8"));
if (!Array.isArray(ledger.quotes) || !Array.isArray(ledger.returnQuotes)) throw new Error("Invalid exchange ledger schema");
const remote = await d1("/internal/open-quotes");
const priceState = await d1("/v1/price");
const validPrice = value => typeof value === "string" &&
  /^\d+(?:\.\d{1,18})?$/.test(value) && Number.isFinite(Number(value)) && Number(value) > 0;
if (!priceState || !validPrice(priceState.price)) {
  throw new Error("D1 did not return a valid confirmed exchange price; refusing to replace it with the opening price");
}
if (ledger.currentPriceUsdtPerSoby === undefined || ledger.currentPriceUsdtPerSoby === null) {
  ledger.currentPriceUsdtPerSoby = priceState.price;
}
if (!validPrice(ledger.currentPriceUsdtPerSoby)) {
  throw new Error("Settlement ledger contains an invalid current exchange price");
}
let changed = false;
for (const quote of remote.quotes || []) {
  const collection = quote.chainId === 1 ? ledger.quotes : ledger.returnQuotes;
  if (!collection.some(existing => existing.orderId === quote.orderId)) {
    const mapped = { ...quote };
    if (quote.chainId === 1) {
      if (!/^0x[0-9a-fA-F]{40}$/.test(mapped.tokenAddress || "")) throw new Error("D1 buy quote has invalid USDT token address");
      mapped.depositTxHash = undefined;
    }
    collection.push(mapped);
    changed = true;
  }
}
let ledgerSha = ledgerFile.sha;
if (changed) {
  ledger.lastUpdatedAt = new Date().toISOString();
  const saved = await gh("/contents/auto-exchange/ledger.json", { method: "PUT",
    body: JSON.stringify({ message: "Import D1 Auto Exchange reservations into settlement ledger",
      content: Buffer.from(JSON.stringify(ledger, null, 2) + "\n").toString("base64"),
      sha: ledgerSha, branch: "main" }) });
  ledgerSha = saved.content.sha;
}
const sync = await d1("/internal/sync-ledger", { method: "POST",
  body: JSON.stringify({ quotes: ledger.quotes, returnQuotes: ledger.returnQuotes, currentPriceUsdtPerSoby: ledger.currentPriceUsdtPerSoby }) });
console.log("D1 quote bridge complete. Imported " + (changed ? "new" : "no new") +
  " reservations; synchronized " + sync.updated + " order states.");
