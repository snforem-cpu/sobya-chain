import { createRpc } from "./rpc.js";
import { classifySearch, formatSoby, shortHash, toDecimal } from "./core.js";
const $ = id => document.getElementById(id);
const rpc = createRpc();
const setText = (id, value) => { $(id).textContent = value; };
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" })[c]);
function row(label, value, { link = false, mono = true, html = false } = {}) {
  const rendered = html ? String(value) : link ? '<a class="link" href="' + escapeHtml(link) + '">' + escapeHtml(value) + '</a>' : escapeHtml(value);
  return '<div class="detail-row"><span>' + escapeHtml(label) + '</span><strong' + (mono ? ' class="mono"' : '') + '>' + rendered + '</strong></div>';
}
function showResult(title, html) {
  setText("resultTitle", title);
  $("resultContent").innerHTML = html;
  $("resultSection").classList.remove("hidden");
  $("resultSection").scrollIntoView({ behavior: "smooth", block: "start" });
}
function errorResult(message) {
  showResult("Unable to complete search", '<p class="muted">' + escapeHtml(message) + '</p>');
}
async function getTransaction(hash) {
  const [tx, receipt] = await Promise.all([
    rpc.request("eth_getTransactionByHash", [hash]),
    rpc.request("eth_getTransactionReceipt", [hash])
  ]);
  if (!tx) throw new Error("Transaction not found on the SOBYA RPC. Check the hash and try again.");
  let block = null;
  if (tx.blockNumber) block = await rpc.request("eth_getBlockByNumber", [tx.blockNumber, false]);
  const status = receipt ? (receipt.status === "0x1" ? "Success" : "Failed") : "Pending / receipt unavailable";
  const gasUsed = receipt?.gasUsed ? BigInt(receipt.gasUsed) : null;
  const effectivePrice = receipt?.effectiveGasPrice ? BigInt(receipt.effectiveGasPrice) : null;
  const fee = gasUsed !== null && effectivePrice !== null ? formatSoby((gasUsed * effectivePrice).toString()) : "—";
  const timestamp = block?.timestamp ? new Date(Number(BigInt(block.timestamp)) * 1000).toLocaleString() : "—";
  const details = [
    row("Transaction hash", tx.hash),
    row("Status", '<span class="pill ' + (status === "Success" ? "success" : status === "Failed" ? "failure" : "pending") + '">' + status + '</span>', { mono:false, html:true }),
    row("Block", tx.blockNumber ? toDecimal(tx.blockNumber) : "Pending", { link: tx.blockNumber ? "?block=" + toDecimal(tx.blockNumber) : null }),
    row("Timestamp", timestamp, { mono:false }),
    row("From", tx.from, { link: "?address=" + tx.from }),
    row("To", tx.to || "Contract creation", { link: tx.to ? "?address=" + tx.to : null }),
    row("Value", formatSoby(tx.value)),
    row("Transaction fee", fee),
    row("Gas limit", toDecimal(tx.gas)),
    row("Gas used", receipt?.gasUsed ? toDecimal(receipt.gasUsed) : "—"),
    row("Gas price", tx.gasPrice ? formatSoby(tx.gasPrice) : "—"),
    row("Nonce", toDecimal(tx.nonce)),
    row("Transaction index", receipt?.transactionIndex ? toDecimal(receipt.transactionIndex) : "—"),
    row("Input data", tx.input && tx.input !== "0x" ? shortHash(tx.input, 26, 18) : "0x (no input data)")
  ].join("");
  showResult("Transaction details", '<div class="detail-grid">' + details + '</div>');
}
async function getBlock(number) {
  const block = await rpc.request("eth_getBlockByNumber", ["0x" + BigInt(number).toString(16), true]);
  if (!block) throw new Error("Block not found.");
  const txs = Array.isArray(block.transactions) ? block.transactions : [];
  const time = new Date(Number(BigInt(block.timestamp)) * 1000).toLocaleString();
  const details = [
    row("Block number", toDecimal(block.number)),
    row("Timestamp", time, { mono:false }),
    row("Block hash", block.hash),
    row("Parent hash", block.parentHash),
    row("Transactions", String(txs.length)),
    row("Gas used", toDecimal(block.gasUsed)),
    row("Gas limit", toDecimal(block.gasLimit)),
    row("Miner / proposer field", block.miner || "Not provided"),
    row("Base fee", block.baseFeePerGas ? formatSoby(block.baseFeePerGas) : "Not provided")
  ].join("");
  const txList = txs.length ? '<div class="blocks">' + txs.slice(0, 40).map(tx => '<div class="block-row"><div><a href="?tx=' + escapeHtml(tx.hash) + '">' + escapeHtml(shortHash(tx.hash)) + '</a><small>Transaction hash</small></div><div>' + escapeHtml(shortHash(tx.from)) + '<small>From</small></div><div>' + escapeHtml(tx.to ? shortHash(tx.to) : "Contract creation") + '<small>To</small></div><div>' + escapeHtml(formatSoby(tx.value)) + '<small>Value</small></div></div>').join("") + '</div>' : '<p class="empty">No transactions in this block.</p>';
  showResult("Block details", '<div class="detail-grid">' + details + '</div><h3 class="subhead">Transactions in this block</h3>' + txList);
}
async function getAddress(address) {
  const [balance, nonce, code] = await Promise.all([
    rpc.request("eth_getBalance", [address, "latest"]),
    rpc.request("eth_getTransactionCount", [address, "latest"]),
    rpc.request("eth_getCode", [address, "latest"])
  ]);
  const isContract = code && code !== "0x";
  const details = [
    row("Address", address),
    row("Native balance", formatSoby(balance)),
    row("Transaction count (nonce)", toDecimal(nonce)),
    row("Address type", isContract ? "Contract (bytecode detected)" : "EOA or address without deployed code", { mono:false }),
    row("Bytecode size", isContract ? Math.max(0, (code.length - 2) / 2) + " bytes" : "0 bytes", { mono:false })
  ].join("");
  showResult("Address overview", '<div class="detail-grid">' + details + '</div><p class="muted">This RPC-only view reports the current balance, nonce and contract-code status. It does not claim to provide a complete historical transaction list.</p>');
}
async function search(value) {
  const query = classifySearch(value);
  $("searchForm").querySelector("button").disabled = true;
  try {
    await rpc.assertNetwork();
    if (query.type === "transaction") await getTransaction(query.value);
    else if (query.type === "address") await getAddress(query.value);
    else await getBlock(query.value);
  } catch (error) { errorResult(error.message || String(error)); }
  finally { $("searchForm").querySelector("button").disabled = false; }
}
async function loadBlocks() {
  const target = $("blocks");
  target.innerHTML = '<div class="empty">Loading live blocks…</div>';
  try {
    const latest = await rpc.request("eth_blockNumber");
    const head = BigInt(latest);
    setText("latestBlock", head.toLocaleString("en-US"));
    setText("blockAge", "Current chain height");
    const count = 8;
    const heights = Array.from({ length: count }, (_, i) => head - BigInt(i)).filter(n => n >= 0n);
    const blocks = await Promise.all(heights.map(n => rpc.request("eth_getBlockByNumber", ["0x" + n.toString(16), false])));
    target.innerHTML = blocks.filter(Boolean).map(block => {
      const height = toDecimal(block.number);
      const date = new Date(Number(BigInt(block.timestamp)) * 1000).toLocaleString();
      return '<div class="block-row"><div><a href="?block=' + height + '">' + height + '</a><small>' + escapeHtml(date) + '</small></div><div>' + escapeHtml(shortHash(block.hash)) + '<small>Block hash</small></div><div>' + escapeHtml(String(block.transactions.length)) + '<small>Transactions</small></div><div>' + escapeHtml(toDecimal(block.gasUsed)) + '<small>Gas used</small></div></div>';
    }).join("") || '<div class="empty">No block data returned.</div>';
  } catch (error) {
    target.innerHTML = '<div class="empty">' + escapeHtml(error.message || String(error)) + '</div>';
  }
}
async function healthCheck() {
  const started = performance.now();
  try {
    await rpc.assertNetwork();
    const elapsed = Math.round(performance.now() - started);
    $("networkStatus").textContent = "SOBYA Mainnet connected";
    $("networkStatus").parentElement.classList.add("online");
    setText("rpcState", "Online");
    setText("rpcLatency", elapsed + " ms response");
    await loadBlocks();
  } catch (error) {
    $("networkStatus").textContent = "RPC unavailable";
    $("networkStatus").parentElement.classList.add("offline");
    setText("rpcState", "Offline");
    setText("rpcLatency", error.message || "Connection failed");
    $("blocks").innerHTML = '<div class="empty">Unable to load live blocks. Please retry when the SOBYA RPC is reachable.</div>';
  }
}
$("searchForm").addEventListener("submit", event => { event.preventDefault(); search($("searchInput").value); });
$("refreshBlocks").addEventListener("click", loadBlocks);
$("clearResult").addEventListener("click", () => $("resultSection").classList.add("hidden"));
const params = new URLSearchParams(location.search);
const initial = params.get("tx") || params.get("address") || params.get("block");
if (initial) $("searchInput").value = initial;
healthCheck().then(() => { if (initial) search(initial); });
