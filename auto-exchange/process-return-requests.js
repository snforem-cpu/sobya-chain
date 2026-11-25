import { readFile } from "node:fs/promises";
import { createReturnQuote, parseReturnIssueBody, formatSobyAtomic, formatUsdtAtomic } from "./return-ledger.js";
import { AUTO_EXCHANGE_POLICY } from "./config.js";

if (!AUTO_EXCHANGE_POLICY.tradingEnabled) {
  console.log("Auto Exchange quote issuance is disabled by shared project policy.");
  process.exit(0);
}

const token = process.env.GH_TOKEN;
const repository = process.env.GH_REPOSITORY;
if (!token || !repository) throw new Error("GH_TOKEN and GH_REPOSITORY are required");
const api = "https://api.github.com/repos/" + repository;
async function request(path, options = {}) {
  const response = await fetch(api + path, {
    ...options,
    headers: { accept: "application/vnd.github+json", authorization: "Bearer " + token,
      "x-github-api-version": "2022-11-28",
      ...(options.body ? { "content-type": "application/json" } : {}), ...options.headers }
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error("GitHub API " + response.status + ": " + JSON.stringify(body));
  return body;
}
async function listPendingIssues() {
  const all = [];
  for (let page = 1; page <= 10; page++) {
    const items = await request("/issues?state=open&per_page=100&page=" + page);
    all.push(...items.filter(item => !item.pull_request && item.title.startsWith("[AUTO-EXCHANGE RETURN]")));
    if (items.length < 100) break;
  }
  return all.sort((a, b) => a.number - b.number);
}
async function saveLedger(ledger, sha) {
  const content = Buffer.from(JSON.stringify(ledger, null, 2) + "\n").toString("base64");
  return request("/contents/auto-exchange/ledger.json", { method: "PUT",
    body: JSON.stringify({ message: "Persist SOBYA SOBY-return quote reservations", content, sha, branch: "main" }) });
}
async function listComments(issueNumber) { return request("/issues/" + issueNumber + "/comments?per_page=100"); }
async function addComment(issueNumber, body) {
  return request("/issues/" + issueNumber + "/comments", { method: "POST", body: JSON.stringify({ body }) });
}
function quoteComment(q) {
  return [
    "## SOBYA Auto Exchange — SOBY return quote reserved", "",
    "- **Order:** " + q.orderId,
    "- **Your USDT refund wallet:** \`" + q.sender + "\`",
    "- **Exact SOBY return:** **" + formatSobyAtomic(q.paymentAmountAtomic) + " SOBY**",
    "- **Quoted USDT refund (after 1% exchange fee, before network fee):** **" + formatUsdtAtomic(q.payoutAmountAtomic) + " USDT**",
    "- **Ethereum network fee:** deducted from this refund using a fresh Chainlink ETH/USD price; the final net USDT is recorded after confirmation.",
    "- **Quoted price:** " + q.quotedPrice + " USDT/SOBY",
    "- **Return network:** SOBYA EVM",
    "- **Return address:** \`" + q.depositAddress + "\`",
    "- **Valid until:** " + q.expiresAt, "",
    "**Funding note:** USDT refunds are processed after the SOBY return is confirmed. If the inventory wallet does not yet have enough USDT and ETH for the refund and Ethereum gas, the order remains safely queued in a funding-wait state and is retried automatically after funds arrive. Do not send more than the exact quoted SOBY amount."
  ].join("\n");
}
const ledger = JSON.parse(await readFile("auto-exchange/ledger.json", "utf8"));
if (!Array.isArray(ledger.returnQuotes)) ledger.returnQuotes = [];
let metadata = await request("/contents/auto-exchange/ledger.json?ref=main");
let ledgerSha = metadata.sha;
const pending = await listPendingIssues();
let changed = false;
const errors = [];
for (const issue of pending) {
  if (ledger.returnQuotes.some(q => q.requestIssueNumber === issue.number)) continue;
  try {
    const fields = parseReturnIssueBody(issue.body || "");
    const result = createReturnQuote({ ledger, issueNumber: issue.number,
      sender: fields.sender, requestedAmount: fields.requestedAmount, now: new Date() });
    ledger.returnQuotes = result.ledger.returnQuotes;
    changed = true;
  } catch (error) { errors.push({ issueNumber: issue.number, message: String(error.message || error) }); }
}
if (changed) {
  ledger.lastUpdatedAt = new Date().toISOString();
  const saved = await saveLedger(ledger, ledgerSha);
  ledgerSha = saved.content.sha;
}
for (const q of ledger.returnQuotes) {
  if (q.notificationPosted === true) continue;
  const comments = await listComments(q.requestIssueNumber);
  const marker = "<!-- sobya-auto-exchange-return:" + q.orderId + " -->";
  if (!comments.some(c => (c.body || "").includes(marker))) await addComment(q.requestIssueNumber, marker + "\n" + quoteComment(q));
  q.notificationPosted = true;
  changed = true;
}
if (changed) {
  ledger.lastUpdatedAt = new Date().toISOString();
  await saveLedger(ledger, ledgerSha);
}
for (const item of errors) {
  const comments = await listComments(item.issueNumber);
  const marker = "<!-- sobya-auto-exchange-return-invalid:" + item.issueNumber + " -->";
  if (!comments.some(c => (c.body || "").includes(marker))) {
    await addComment(item.issueNumber, marker + "\nReturn quote request could not be issued: " + item.message + ". Please edit the issue to correct the fields.");
  }
}
console.log("Scanned " + pending.length + " SOBY return requests; ledger contains " + ledger.returnQuotes.length + " return quotes.");
