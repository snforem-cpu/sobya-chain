import { Interface } from "https://esm.sh/ethers@6.13.5";
import { isTransactionHash, isContractProofRecord } from "./proof-core.js";

const CHAIN_ID = 357812033857n;
const CHAIN_HEX = "0x534f425941";
const REGISTRY_ADDRESS = "0x9B1C6Cc504DEb8FA7aB9DAe499aB3D042fEC97b9";
const SERVICE_WALLET = "0xd316993423Fc6268038F4EE3EA7C0C5038513C18";
const proofInterface = new Interface([
  "function recordProof(bytes32 documentHash) payable",
  "function feeRecipient() view returns (address)",
  "event ProofRecorded(address indexed submitter, bytes32 indexed documentHash, uint256 fee, uint256 timestamp)"
]);
const SERVICE_FEE_WEI = 1000000000000000000n;
const RPCS = [
  "https://sobya-evm-rpc.nodesafe-dapp.xyz",
  "https://sobya-evm-rpc.nodesafe-app.xyz"
];
const $ = id => document.getElementById(id);
const state = { wallet: null, account: null, file: null, hash: null, lang: "en" };

function message(element, text, kind = "") {
  element.textContent = text;
  element.className = kind ? `result ${kind}` : "result";
  element.hidden = false;
}
function setWallet(text) { $("wallet-state").textContent = text; }
function setBusy(button, busy, label) {
  button.disabled = busy;
  if (busy) button.dataset.oldLabel = button.textContent;
  button.textContent = busy ? label : (button.dataset.oldLabel || button.textContent);
}
function bytesToHex(bytes) {
  return "0x" + Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}
async function fingerprint(file) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return bytesToHex(new Uint8Array(digest));
}
function setLanguage(lang) {
  state.lang = lang;
  window.dispatchEvent(new CustomEvent("sobya:language", { detail: lang }));
  document.documentElement.lang = lang;
  document.body.dir = lang === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-en][data-ar]").forEach(node => {
    node.textContent = node.dataset[lang];
  });
  $("language").textContent = lang === "ar" ? "English" : "العربية";
  $("file-hash").textContent = state.hash || (lang === "ar" ? "لم تُحسب بعد" : "Not calculated yet");
  $("file-name").textContent = state.file?.name || (lang === "ar" ? "تتم معالجة الملف محلياً ولا يتم رفعه." : "The file is processed locally and is never uploaded.");
}
let evmClient = null;
let connectorPromise = null;
let boundProvider = null;
let connectedViaSdk = false;

async function initWalletConnector() {
  try {
    const mod = await import("https://esm.sh/@metamask/connect-evm@2.1.1?bundle");
    evmClient = await mod.createEVMClient({
      dapp: {
        name: "SOBYA Proof",
        url: window.location.href,
        iconUrl: new URL("../assets/logo/sobya-coin-128.png", window.location.href).href
      },
      api: { supportedNetworks: { [CHAIN_HEX]: RPCS[0] } },
      analytics: { enabled: false }
    });
    return evmClient;
  } catch (error) {
    console.warn("MetaMask Connect unavailable; injected wallet connection remains available.", error);
    return null;
  }
}
connectorPromise = initWalletConnector();

function findInjectedProvider() {
  const injected = window.ethereum;
  const providers = injected && Array.isArray(injected.providers) ? injected.providers : [];
  return providers.find(provider => provider && provider.isMetaMask) || injected || null;
}

function bindWalletEvents(provider) {
  if (!provider || typeof provider.on !== "function" || boundProvider === provider) return;
  boundProvider = provider;
  provider.on("accountsChanged", accounts => {
    state.account = accounts?.[0] || null;
    setWallet(state.account ? `Connected: ${state.account}` : "Wallet disconnected. Reconnect to continue.");
    $("record-button").disabled = !state.hash || !state.account;
    window.dispatchEvent(new CustomEvent("sobya:wallet", { detail: { provider, account: state.account } }));
  });
  provider.on("chainChanged", () => {
    state.account = null;
    $("record-button").disabled = true;
    window.dispatchEvent(new CustomEvent("sobya:wallet", { detail: { provider, account: null } }));
    setWallet("Network changed. Reconnect to SOBYA Mainnet.");
  });
}
async function ensureSobyaNetwork(provider) {
  const current = await provider.request({ method: "eth_chainId" });
  if (BigInt(current) === CHAIN_ID) return;
  const chainConfiguration = {
    chainId: CHAIN_HEX,
    chainName: "SOBYA Mainnet",
    nativeCurrency: { name: "SOBY", symbol: "SOBY", decimals: 18 },
    rpcUrls: RPCS,
    blockExplorerUrls: ["https://explorer.nodesafe-app.xyz/sobya"]
  };
  if (connectedViaSdk && evmClient && typeof evmClient.switchChain === "function") {
    await evmClient.switchChain({ chainId: CHAIN_HEX, chainConfiguration });
  } else {
    try {
      await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
    } catch (error) {
      if (error.code !== 4902) throw error;
      await provider.request({ method: "wallet_addEthereumChain", params: [chainConfiguration] });
      await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
    }
  }
  const verifiedChain = await provider.request({ method: "eth_chainId" });
  if (BigInt(verifiedChain) !== CHAIN_ID) {
    throw new Error("MetaMask did not switch to SOBYA Mainnet. Reconnect the wallet and try again.");
  }
}
async function connectWallet() {
  let provider = null;
  let accounts = [];

  // Follow SOBYA Auto Exchange: MetaMask Connect SDK first, injected provider fallback.
  try {
    const client = await Promise.race([
      connectorPromise,
      new Promise(resolve => setTimeout(() => resolve(null), 7000))
    ]);
    if (client) {
      const session = await client.connect({ chainIds: [CHAIN_HEX], forceRequest: true });
      provider = client.getProvider();
      connectedViaSdk = Boolean(provider);
      const sessionAccounts = session && Array.isArray(session.accounts) ? session.accounts : [];
      accounts = sessionAccounts
        .map(item => typeof item === "string" ? item : (item && typeof item.address === "string" ? item.address : null))
        .filter(Boolean);
      if (!accounts.length && provider) {
        accounts = await provider.request({ method: "eth_accounts", params: [] });
      }
    }
  } catch (error) {
    console.warn("MetaMask Connect flow unavailable; trying injected wallet fallback:", error);
  }

  if (!provider || !accounts?.[0]) {
    provider = findInjectedProvider();
    connectedViaSdk = false;
    if (!provider || typeof provider.request !== "function") {
      throw new Error("MetaMask connection is unavailable. Open MetaMask or use its in-app browser, then try again.");
    }
    accounts = await provider.request({ method: "eth_requestAccounts", params: [] });
  }

  if (!provider || !accounts?.[0]) {
    throw new Error("MetaMask did not return an account. Unlock your wallet and approve the connection.");
  }

  state.wallet = provider;
  await ensureSobyaNetwork(provider);
  const currentAccounts = await provider.request({ method: "eth_accounts", params: [] });
  state.account = currentAccounts?.[0] || accounts[0];
  window.dispatchEvent(new CustomEvent("sobya:wallet", { detail: { provider, account: state.account } }));
  bindWalletEvents(provider);
  setWallet(`Connected: ${state.account}`);
  $("record-button").disabled = !state.hash;
}
async function rpc(method, params) {
  let lastError;
  for (const url of RPCS) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params })
      });
      if (!response.ok) throw new Error(`RPC HTTP ${response.status}`);
      const body = await response.json();
      if (body.error) throw new Error(body.error.message || "RPC request failed");
      return body.result;
    } catch (error) { lastError = error; }
  }
  if (state.wallet) {
    const chain = await state.wallet.request({ method: "eth_chainId" });
    if (BigInt(chain) === CHAIN_ID) return state.wallet.request({ method, params });
  }
  throw new Error(lastError?.message || "Unable to reach a SOBYA RPC endpoint.");
}
async function calculateSelectedFile(inputId = "file") {
  const file = $(inputId).files?.[0];
  if (!file) throw new Error("Choose a file first.");
  const hash = await fingerprint(file);
  if (inputId === "file") {
    state.file = file;
    state.hash = hash;
    $("file-name").textContent = file.name;
    $("file-hash").textContent = hash;
    $("record-button").disabled = !state.account;
  }
  return hash;
}
async function recordProof() {
  if (!state.hash) throw new Error("Calculate the file fingerprint first.");
  if (!state.wallet || !state.account) {
    throw new Error("Connect MetaMask first. Once the wallet is connected and its address appears here, press Register on SOBYA again to request the payment approval.");
  }
  await ensureSobyaNetwork(state.wallet);
  const code = await rpc("eth_getCode", [REGISTRY_ADDRESS, "latest"]);
  if (!code || code === "0x") throw new Error("The official SOBYA Proof Registry contract is not available at its configured address.");
  const recipient = await rpc("eth_call", [{ to: REGISTRY_ADDRESS, data: proofInterface.encodeFunctionData("feeRecipient") }, "latest"]);
  const verifiedRecipient = "0x" + recipient.slice(-40);
  if (verifiedRecipient.toLowerCase() !== SERVICE_WALLET.toLowerCase()) {
    throw new Error("The deployed Proof Registry fee recipient does not match the official service wallet. Registration is disabled.");
  }
  const data = proofInterface.encodeFunctionData("recordProof", [state.hash]);
  setWallet("Opening MetaMask transaction approval…");
  let txHash;
  const transaction = { from: state.account, to: REGISTRY_ADDRESS, value: "0x" + SERVICE_FEE_WEI.toString(16), data };
  try {
    // Use the connected EIP-1193 provider for the transaction approval.
    // This avoids the SDK connectWith handoff path, which can return a rejection
    // before MetaMask displays the transaction details on mobile browsers.
    txHash = await state.wallet.request({
      method: "eth_sendTransaction",
      params: [transaction]
    });
    if (!isTransactionHash(txHash)) throw new Error("MetaMask returned no valid transaction hash.");
  } catch (error) {
    const code = error?.rpcCode ?? error?.code;
    const dataDetail = error?.rpcData ?? error?.data;
    const detail = error?.shortMessage || error?.info?.error?.message || error?.message || "MetaMask did not approve the transaction.";
    if (code === 4001 || code === "ACTION_REJECTED") throw new Error("Transaction approval was rejected in MetaMask.");
    if (code === -32002) throw new Error("A MetaMask request is already pending. Open MetaMask and finish or cancel it.");
    const extra = dataDetail ? " Details: " + (typeof dataDetail === "string" ? dataDetail : JSON.stringify(dataDetail)) : "";
    throw new Error("MetaMask transaction request failed" + (code !== undefined ? " (code " + code + ")" : "") + ": " + detail + extra);
  }
  const result = $("record-result");
  message(result, `1 SOBY service fee submitted to ${SERVICE_WALLET}. Wait for confirmation, then verify your paid proof here. Transaction: ${txHash}`);
  result.classList.add("success");
  setWallet(`Proof submitted with 1 SOBY service fee: ${txHash}`);
}
$("file").addEventListener("change", async () => {
  state.file = $("file").files?.[0] || null;
  state.hash = null;
  $("record-button").disabled = true;
  if (!state.file) {
    $("file-name").textContent = state.lang === "ar" ? "لم يتم اختيار ملف." : "No file selected.";
    $("file-hash").textContent = state.lang === "ar" ? "لم تُحسب بعد" : "Not calculated yet";
    return;
  }
  $("file-name").textContent = state.file.name;
  $("file-hash").textContent = state.lang === "ar" ? "جارٍ حساب البصمة محلياً…" : "Calculating locally…";
  try {
    await calculateSelectedFile();
    setWallet(state.lang === "ar"
      ? "تم اختيار الملف وحساب بصمته على جهازك. لم يتم رفع الملف."
      : "File selected and fingerprint calculated on your device. The file was not uploaded.");
  } catch (error) {
    $("file-hash").textContent = state.lang === "ar" ? "تعذر حساب البصمة" : "Fingerprint calculation failed";
    setWallet(error.message);
  }
});
$("hash-button").addEventListener("click", async () => {
  const button = $("hash-button");
  try {
    setBusy(button, true, state.lang === "ar" ? "جارٍ الحساب…" : "Calculating…");
    await calculateSelectedFile();
  } catch (error) { setWallet(error.message); }
  finally { setBusy(button, false); }
});
$("connect-button").addEventListener("click", async () => {
  try { await connectWallet(); }
  catch (error) { setWallet(error.message); }
});
$("record-button").addEventListener("click", async () => {
  const button = $("record-button");
  try {
    setBusy(button, true, state.lang === "ar" ? "افتح محفظتك…" : "Check wallet…");
    await recordProof();
  } catch (error) { setWallet(error.message); }
  finally { button.textContent = state.lang === "ar" ? "سجّل على SOBYA" : "Register on SOBYA"; button.disabled = !state.hash || !state.account; }
});
$("language").addEventListener("click", () => setLanguage(state.lang === "en" ? "ar" : "en"));
bindWalletEvents(findInjectedProvider());

// Restore an already-approved wallet session after MetaMask's mobile app handoff
// or a browser reload. This is read-only: eth_accounts never opens an approval prompt.
async function restoreWalletSession() {
  try {
    let provider = findInjectedProvider();
    if (!provider) {
      const client = await connectorPromise;
      provider = client && typeof client.getProvider === "function" ? client.getProvider() : null;
      connectedViaSdk = Boolean(provider);
    }
    if (!provider || typeof provider.request !== "function") return;
    const accounts = await provider.request({ method: "eth_accounts", params: [] });
    if (!accounts || !accounts.length) return;
    state.wallet = provider;
    state.account = accounts[0];
    window.dispatchEvent(new CustomEvent("sobya:wallet", { detail: { provider, account: state.account } }));
    bindWalletEvents(provider);
    setWallet(`Connected: ${state.account}`);
    $("record-button").disabled = !state.hash;
  } catch (error) {
    console.warn("Could not restore the existing MetaMask session:", error);
  }
}
restoreWalletSession();
