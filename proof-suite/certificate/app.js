import { Interface } from "https://esm.sh/ethers@6.13.5";
import QRCode from "https://esm.sh/qrcode@1.5.4?bundle";
import { computeCertificateHash, generateCertificateId, isCertificateId } from "./core.js";
import { isTransactionHash, isValidRegistryRecord } from "../invoice-proof/core.js";

const CHAIN_ID = 357812033857n;
const CHAIN_HEX = "0x534f425941";
const REGISTRY = "0x9B1C6Cc504DEb8FA7aB9DAe499aB3D042fEC97b9";
const RECIPIENT = "0xd316993423Fc6268038F4EE3EA7C0C5038513C18";
const FEE = 1000000000000000000n;
const RPCS = ["https://sobya-evm-rpc.nodesafe-dapp.xyz", "https://sobya-evm-rpc.nodesafe-app.xyz"];
const abi = new Interface([
  "function recordProof(bytes32 documentHash) payable",
  "function feeRecipient() view returns (address)",
  "event ProofRecorded(address indexed submitter,bytes32 indexed documentHash,uint256 fee,uint256 timestamp)"
]);
const $ = id => document.getElementById(id);
const state = { provider: null, account: null, lang: "en", certificateId: null };

function say(id, text, kind = "") {
  const element = $(id);
  element.textContent = text;
  element.className = kind ? "result " + kind : "result";
  element.hidden = false;
}
function setWallet(text) { $("certificate-wallet-state").textContent = text; }
function getMetadata(prefix = "cert-") {
  const verify = prefix === "verify-cert-";
  const id = verify ? "verify-cert-id" : "cert-id";
  return {
    certificateId: verify ? $(id).value.trim() : state.certificateId,
    issuer: $(verify ? "verify-cert-issuer" : "cert-issuer").value,
    recipient: $(verify ? "verify-cert-recipient" : "cert-recipient").value,
    title: $(verify ? "verify-cert-title" : "cert-title").value,
    issueDate: $(verify ? "verify-cert-issue-date" : "cert-issue-date").value,
    expiryDate: $(verify ? "verify-cert-expiry-date" : "cert-expiry-date").value,
    notes: $(verify ? "verify-cert-notes" : "cert-notes").value
  };
}
function provider() {
  const injected = window.ethereum;
  const providers = injected && Array.isArray(injected.providers) ? injected.providers : [];
  return providers.find(item => item?.isMetaMask) || injected || null;
}
function bindWallet(p) {
  if (!p?.request || typeof p.on !== "function") return;
  p.on("accountsChanged", accounts => {
    state.account = accounts?.[0] || null;
    state.provider = p;
    setWallet(state.account ? "Connected: " + state.account : "Wallet disconnected. Connect in SOBYA Proof above.");
  });
  p.on("chainChanged", () => {
    state.account = null;
    setWallet("Network changed. Reconnect in SOBYA Proof.");
  });
}
window.addEventListener("sobya:wallet", event => {
  state.provider = event.detail?.provider || state.provider;
  state.account = event.detail?.account || null;
  setWallet(state.account ? "Connected: " + state.account : "Connect your wallet in SOBYA Proof above.");
});
window.addEventListener("sobya:language", event => { state.lang = event.detail === "ar" ? "ar" : "en"; });

async function restoreWallet() {
  try {
    const p = provider();
    if (!p?.request) return;
    bindWallet(p);
    const accounts = await p.request({ method: "eth_accounts", params: [] });
    if (accounts?.[0]) {
      state.provider = p;
      state.account = accounts[0];
      setWallet("Connected: " + state.account);
    }
  } catch (error) { console.warn("Certificate wallet restore failed:", error); }
}
async function ensureNetwork(p) {
  if (BigInt(await p.request({ method: "eth_chainId" })) === CHAIN_ID) return;
  const config = {
    chainId: CHAIN_HEX, chainName: "SOBYA Mainnet",
    nativeCurrency: { name: "SOBY", symbol: "SOBY", decimals: 18 },
    rpcUrls: RPCS, blockExplorerUrls: ["https://explorer.nodesafe-app.xyz/sobya"]
  };
  try {
    await p.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await p.request({ method: "wallet_addEthereumChain", params: [config] });
    await p.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
  }
  if (BigInt(await p.request({ method: "eth_chainId" })) !== CHAIN_ID) throw new Error("MetaMask did not switch to SOBYA Mainnet.");
}
async function rpc(method, params) {
  let last;
  for (const url of RPCS) {
    try {
      const response = await fetch(url, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params })
      });
      if (!response.ok) throw new Error("RPC HTTP " + response.status);
      const body = await response.json();
      if (body.error) throw new Error(body.error.message || "RPC request failed");
      return body.result;
    } catch (error) { last = error; }
  }
  if (state.provider && BigInt(await state.provider.request({ method: "eth_chainId" })) === CHAIN_ID) {
    return state.provider.request({ method, params });
  }
  throw new Error(last?.message || "Unable to reach SOBYA RPC.");
}
async function checkRegistry() {
  const code = await rpc("eth_getCode", [REGISTRY, "latest"]);
  if (!code || code === "0x") throw new Error("The SOBYA Proof Registry contract is unavailable.");
  const encoded = abi.encodeFunctionData("feeRecipient");
  const result = await rpc("eth_call", [{ to: REGISTRY, data: encoded }, "latest"]);
  if (("0x" + result.slice(-40)).toLowerCase() !== RECIPIENT.toLowerCase()) {
    throw new Error("The registry recipient does not match the configured SOBYA service wallet.");
  }
}
function issueMetadata() {
  if (!state.certificateId) state.certificateId = generateCertificateId();
  return {
    certificateId: state.certificateId,
    issuer: $("cert-issuer").value,
    recipient: $("cert-recipient").value,
    title: $("cert-title").value,
    issueDate: $("cert-issue-date").value,
    expiryDate: $("cert-expiry-date").value,
    notes: $("cert-notes").value
  };
}
const CERTIFICATE_STORAGE_KEY = "sobya:last-issued-certificate:v1";
function displayCertificatePreview(metadata, tx, status) {
  $("certificate-preview-title").textContent = metadata.title;
  $("certificate-preview-recipient").textContent = metadata.recipient;
  $("certificate-preview-issuer").textContent = metadata.issuer;
  $("certificate-preview-issue-date").textContent = metadata.issueDate;
  $("certificate-preview-expiry").textContent = metadata.expiryDate ? " · Expires: " + metadata.expiryDate : "";
  $("certificate-preview-notes").textContent = metadata.notes;
  $("certificate-preview-id").textContent = metadata.certificateId;
  $("certificate-preview-tx").textContent = tx || "Pending transaction hash";
  $("certificate-preview-status").textContent = status;
  $("certificate-preview").hidden = false;
  if (tx) {
    const verifyUrl = new URL("./?cert=" + encodeURIComponent(metadata.certificateId) + "&tx=" + encodeURIComponent(tx) + "#certificate-verify", window.location.href).href;
    return QRCode.toCanvas($("certificate-qr"), verifyUrl, {
      width: 160, margin: 1, color: { dark: "#071426", light: "#ffffff" }
    });
  }
  return Promise.resolve();
}
function saveCertificateRecord(metadata, tx, status) {
  try {
    localStorage.setItem(CERTIFICATE_STORAGE_KEY, JSON.stringify({ metadata, tx, status, savedAt: Date.now() }));
  } catch (error) { console.warn("Could not save certificate recovery data locally:", error); }
}
async function restoreCertificatePreview() {
  try {
    const saved = JSON.parse(localStorage.getItem(CERTIFICATE_STORAGE_KEY) || "null");
    if (!saved?.metadata?.certificateId || !isTransactionHash(saved.tx)) return;
    await displayCertificatePreview(saved.metadata, saved.tx, saved.status || "SUBMITTED — CHECK CONFIRMATION");
  } catch (error) { console.warn("Certificate preview restore failed:", error); }
}
async function issueCertificate() {
  if (!state.provider || !state.account) throw new Error("Connect your wallet in the SOBYA Proof section above first.");
  const metadata = issueMetadata();
  const hash = await computeCertificateHash(metadata);
  const activeProvider = state.provider;
  if (!activeProvider?.request) throw new Error("Wallet provider is unavailable. Reconnect MetaMask in the SOBYA Proof section.");
  await ensureNetwork(activeProvider);
  // Re-read the authorized account immediately before sending; never pass null as transaction.from.
  const accounts = await activeProvider.request({ method: "eth_accounts", params: [] });
  const activeAccount = Array.isArray(accounts) ? accounts.find(account => typeof account === "string" && /^0x[a-fA-F0-9]{40}$/.test(account)) : null;
  if (!activeAccount) {
    state.account = null;
    throw new Error("Your wallet is not connected to this page. Press Connect wallet in the SOBYA Proof section, approve the connection, then try again.");
  }
  state.account = activeAccount;
  await checkRegistry();
  setWallet("Opening MetaMask approval… Review the 1 SOBY service fee and network gas.");
  const transaction = {
    from: activeAccount,
    to: REGISTRY,
    value: "0x" + FEE.toString(16),
    data: abi.encodeFunctionData("recordProof", [hash])
  };
  const tx = await activeProvider.request({
    method: "eth_sendTransaction",
    params: [transaction]
  });
  if (!isTransactionHash(tx)) throw new Error("MetaMask did not return a valid transaction hash.");
  state.certificateId = metadata.certificateId;
  saveCertificateRecord(metadata, tx, "PENDING CONFIRMATION — VERIFY AFTER BLOCK");
  // Reveal and persist the certificate before optional QR generation or receipt polling.
  await displayCertificatePreview(metadata, tx, "PENDING CONFIRMATION — VERIFY AFTER BLOCK");
  say("certificate-issue-result", "Certificate transaction submitted. Save the certificate ID and transaction hash shown below. Transaction: " + tx, "success");
  let receipt = null;
  try { receipt = await rpc("eth_getTransactionReceipt", [tx]); } catch (error) { console.warn("Receipt lookup delayed:", error); }
  if (receipt && receipt.status !== "0x1") {
    $("certificate-preview-status").textContent = "TRANSACTION FAILED";
    saveCertificateRecord(metadata, tx, "TRANSACTION FAILED");
    throw new Error("The certificate transaction failed on SOBYA Mainnet. The transaction details remain visible for reference.");
  }
  const status = receipt ? "ON-CHAIN RECORD CONFIRMED" : "PENDING CONFIRMATION — VERIFY AFTER BLOCK";
  $("certificate-preview-status").textContent = status;
  saveCertificateRecord(metadata, tx, status);
  try {
    await displayCertificatePreview(metadata, tx, status);
  } catch (error) {
    console.warn("QR generation failed; certificate details remain available:", error);
    say("certificate-issue-result", "Certificate submitted. The QR code could not be generated, but the Certificate ID and transaction hash are displayed below and saved in this browser.", "success");
  }
  state.certificateId = null;
  setWallet("Certificate submitted. Its details are saved in this browser and can be restored on this device.");

}
async function verifyCertificate() {
  const txHash = $("verify-cert-tx").value.trim();
  if (!isTransactionHash(txHash)) throw new Error("Enter a valid SOBYA transaction hash.");
  const metadata = getMetadata("verify-cert-");
  if (!isCertificateId(metadata.certificateId)) throw new Error("Enter a valid SOBYA certificate ID.");
  const expected = await computeCertificateHash(metadata);
  const [chain, tx, receipt] = await Promise.all([
    rpc("eth_chainId", []), rpc("eth_getTransactionByHash", [txHash]), rpc("eth_getTransactionReceipt", [txHash])
  ]);
  if (BigInt(chain) !== CHAIN_ID) throw new Error("RPC endpoint is not connected to SOBYA Mainnet.");
  if (!tx) throw new Error("Transaction not found.");
  if (!receipt) throw new Error("Certificate record is not confirmed yet. Try again shortly.");
  if (tx.to?.toLowerCase() !== REGISTRY.toLowerCase()) throw new Error("Transaction does not call the official SOBYA Proof Registry.");
  let call = null, event = null;
  try {
    const parsed = abi.parseTransaction({ data: tx.input || tx.data, value: tx.value });
    if (parsed) call = { name: parsed.name, args: [...parsed.args] };
  } catch {}
  for (const log of receipt.logs || []) {
    if (log.address?.toLowerCase() !== REGISTRY.toLowerCase()) continue;
    try {
      const parsed = abi.parseLog({ topics: log.topics, data: log.data });
      if (parsed?.name === "ProofRecorded") {
        event = { name: parsed.name, args: [parsed.args.submitter, parsed.args.documentHash, parsed.args.fee, parsed.args.timestamp] };
        break;
      }
    } catch {}
  }
  if (!isValidRegistryRecord(tx, receipt, CHAIN_ID, REGISTRY, FEE, call, event)) {
    throw new Error("This is not a valid paid SOBYA Proof Registry record.");
  }
  if (String(call.args[0]).toLowerCase() !== expected.toLowerCase()) {
    throw new Error("NO MATCH: the certificate details do not reproduce the recorded fingerprint.");
  }
  const block = await rpc("eth_getBlockByNumber", [receipt.blockNumber, false]);
  const timestamp = block?.timestamp ? new Date(Number(BigInt(block.timestamp)) * 1000).toLocaleString(state.lang === "ar" ? "ar" : "en") : "Confirmed";
  say("certificate-verify-result",
    "MATCH — certificate details reproduce the registered fingerprint.\nCertificate ID: " + metadata.certificateId +
    "\nIssuer: " + metadata.issuer + "\nRecipient: " + metadata.recipient +
    "\nSigner: " + tx.from + "\nBlock: " + BigInt(receipt.blockNumber).toString() +
    "\nRecorded: " + timestamp + "\nTransaction: " + txHash, "success");
}
$("certificate-issue-button").addEventListener("click", async () => {
  const button = $("certificate-issue-button");
  button.disabled = true;
  try { await issueCertificate(); }
  catch (error) { say("certificate-issue-result", error.message, "error"); }
  finally { button.disabled = false; }
});
$("certificate-verify-button").addEventListener("click", async () => {
  const button = $("certificate-verify-button");
  button.disabled = true;
  try { await verifyCertificate(); }
  catch (error) { say("certificate-verify-result", error.message, "error"); }
  finally { button.disabled = false; }
});
$("certificate-print-button").addEventListener("click", () => window.print());
const today = new Date().toISOString().slice(0, 10);
$("cert-issue-date").value = today;
$("verify-cert-issue-date").value = today;
const query = new URLSearchParams(window.location.search);
if (query.has("cert")) $("verify-cert-id").value = query.get("cert");
if (query.has("tx")) $("verify-cert-tx").value = query.get("tx");
restoreCertificatePreview();
restoreWallet();
