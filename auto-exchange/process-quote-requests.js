import { readFile } from "node:fs/promises";
import { createQuote, parseQuoteIssueBody, formatUsdtAtomic } from "./quote-ledger.js";

const token = process.env.GH_TOKEN;
const repository = process.env.GH_REPOSITORY;
if (!token || !repository) throw new Error("GH_TOKEN and GH_REPOSITORY are required");
const api = "https://api.github.com/repos/" + repository;

async function request(path, options = {}) {
  const response = await fetch(api + path, {
    ...options,
    headers: {
      accept: "application/vnd.github+json",
      authorization: "Bearer " + token,
      "x-github-api-version": "2022-11-28",
      ...(options.body ? { "content-type": "application/json" } : {}),
      ...options.headers
    }
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error("GitHub API " + response.status + ": " + JSON.stringify(body));
  return body;
}
async function listPendingIssues() {
  const all = [];
  for (let page = 1; page <= 10; page++) {
    const items = await request("/issues?state=open&per_page=100&page=" + page);
    all.push(...items.filter(item => !item.pull_request && item.title.startsWith("[AUTO-EXCHANGE QUOTE]")));
    if (items.length < 100) break;
  }
  return all.sort((a, b) => a.number - b.number);
}
async function getLedgerMetadata() {
  return request("/contents/auto-exchange/ledger.json?ref=main");
}
async function saveLedger(ledger, sha) {
  const content = Buffer.from(JSON.stringify(ledger, null, 2) + "\n").toString("base64");
  return request("/contents/auto-exchange/ledger.json", {
    method: "PUT",
    body: JSON.stringify({
      message: "Persist SOBYA Auto Exchange quote reservations",
      content, sha, branch: "main"
    })
  });
}
async function listComments(issueNumber) {
  return request("/issues/" + issueNumber + "/comments?per_page=100");
}
async function addComment(issueNumber, body) {
  return request("/issues/" + issueNumber + "/comments", {
    method: "POST", body: JSON.stringify({ body })
  });
}
function formatSobyAtomic(value) {
  const n = BigInt(value);
  return String(n / (10n ** 18n)) + "." + String(n % (10n ** 18n)).padStart(18, "0").replace(/0+$/, "");
}
function quoteComment(q) {
  return [
    "## SOBYA Auto Exchange — quote reserved",
    "",
    "- **Order:** " + q.orderId,
    "- **Your receiving wallet:** \`" + q.sender + "\`",
    "- **Exact USDT payment:** **" + formatUsdtAtomic(q.paymentAmountAtomic) + " USDT**",
    "- **Quoted SOBY amount (after 1% fee):** **" + formatSobyAtomic(q.payoutAmountAtomic) + " SOBY**",
    "- **Opening price used:** 0.005 USDT/SOBY",
    "- **Deposit network:** Ethereum Mainnet",
    "- **USDT contract:** \`" + q.tokenAddress + "\`",
    "- **Deposit address:** \`" + q.depositAddress + "\`",
    "- **Valid until:** " + q.expiresAt,
    "",
    "**Important: this is a reservation test only. Trading and payouts remain disabled. Do not send USDT.**"
  ].join("\n");
}

const ledgerRaw = await readFile("auto-exchange/ledger.json", "utf8");
let ledger = JSON.parse(ledgerRaw);
if (!Array.isArray(ledger.quotes)) throw new Error("ledger.quotes is missing");
let metadata = await getLedgerMetadata();
let ledgerSha = metadata.sha;
const pending = await listPendingIssues();
let changed = false;
const errors = [];

for (const issue of pending) {
  if (ledger.quotes.some(q => q.requestIssueNumber === issue.number)) continue;
  try {
    const fields = parseQuoteIssueBody(issue.body || "");
    const result = createQuote({
      ledger, issueNumber: issue.number, sender: fields.sender,
      requestedAmount: fields.requestedAmount, now: new Date()
    });
    ledger = result.ledger;
    changed = true;
  } catch (error) {
    errors.push({ issueNumber: issue.number, message: String(error.message || error) });
  }
}
if (changed) {
  ledger.lastUpdatedAt = new Date().toISOString();
  const saved = await saveLedger(ledger, ledgerSha);
  ledgerSha = saved.content.sha;
}

let notificationsChanged = false;
for (const q of ledger.quotes) {
  if (q.notificationPosted === true) continue;
  const comments = await listComments(q.requestIssueNumber);
  const marker = "<!-- sobya-auto-exchange-quote:" + q.orderId + " -->";
  const alreadyPosted = comments.some(c => (c.body || "").includes(marker));
  if (!alreadyPosted) await addComment(q.requestIssueNumber, marker + "\n" + quoteComment(q));
  q.notificationPosted = true;
  notificationsChanged = true;
}
if (notificationsChanged) {
  ledger.lastUpdatedAt = new Date().toISOString();
  await saveLedger(ledger, ledgerSha);
}
for (const item of errors) {
  const comments = await listComments(item.issueNumber);
  const marker = "<!-- sobya-auto-exchange-invalid:" + item.issueNumber + " -->";
  if (!comments.some(c => (c.body || "").includes(marker))) {
    await addComment(item.issueNumber, marker + "\\nQuote request could not be issued: " + item.message + ". Please edit the issue to correct the fields.");
  }
}
console.log("Scanned " + pending.length + " open request issues; ledger now contains " + ledger.quotes.length + " reserved quote records.");
