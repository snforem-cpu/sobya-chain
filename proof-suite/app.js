import { encodeProofPayload, decodeProofPayload, isTransactionHash, isPaidProofRecord } from "./proof-core.js";

const CHAIN_ID = 357812033857n;
const CHAIN_HEX = "0x534f425941";
const SERVICE_WALLET = "0xd316993423Fc6268038F4EE3EA7C0C5038513C18";
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
  });
  provider.on("chainChanged", () => {
    state.account = null;
    $("record-button").disabled = true;
    setWallet("Network changed. Reconnect to SOBYA Mainnet.");
  });
}
async function ensureSobyaNetwork(provider) {
  const current = await provider.request({ method: "eth_chainId" });
  if (BigInt(current) === CHAIN_ID) return;
  try {
    await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await provider.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: CHAIN_HEX,
        chainName: "SOBYA Mainnet",
        nativeCurrency: { name: "SOBY", symbol: "SOBY", decimals: 18 },
        rpcUrls: RPCS,
        blockExplorerUrls: ["https://explorer.nodesafe-app.xyz/sobya"]
      }]
    });
    await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
  }
}
async function connectWallet() {
  let provider = findInjectedProvider();
  let accounts = [];

  // Match SOBYA Auto Exchange: use the injected MetaMask provider first.
  if (provider && typeof provider.request === "function") {
    accounts = await provider.request({ method: "eth_requestAccounts", params: [] });
  } else {
    const client = await Promise.race([
      connectorPromise,
      new Promise(resolve => setTimeout(() => resolve(null), 7000))
    ]);
    if (!client) {
      throw new Error("MetaMask connection is unavailable. Open MetaMask or use its in-app browser, then try again.");
    }
    const session = await client.connect({ chainIds: [CHAIN_HEX], forceRequest: true });
    provider = client.getProvider();
    const sessionAccounts = session && Array.isArray(session.accounts) ? session.accounts : [];
    accounts = sessionAccounts
      .map(item => typeof item === "string" ? item : (item && typeof item.address === "string" ? item.address : null))
      .filter(Boolean);
    if (!accounts.length && provider) {
      accounts = await provider.request({ method: "eth_accounts", params: [] });
    }
  }

  if (!provider || !accounts?.[0]) {
    throw new Error("MetaMask did not return an account. Unlock your wallet and approve the connection.");
  }

  state.wallet = provider;
  await ensureSobyaNetwork(provider);
  const currentAccounts = await provider.request({ method: "eth_accounts", params: [] });
  state.account = currentAccounts?.[0] || accounts[0];
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
  if (!state.wallet || !state.account) await connectWallet();
  await ensureSobyaNetwork(state.wallet);
  const data = encodeProofPayload(state.hash);
  // Estimate the exact self-record transaction before opening MetaMask.
  // Supplying an explicit gas limit avoids wallet-side estimation failures
  // on RPC providers that do not reliably estimate data-bearing self-transfers.
  const txRequest = {
    from: state.account,
    to: SERVICE_WALLET,
    value: "0x" + SERVICE_FEE_WEI.toString(16),
    data
  };
  let estimatedGas;
  try {
    estimatedGas = await rpc("eth_estimateGas", [txRequest]);
  } catch (rpcError) {
    try {
      estimatedGas = await state.wallet.request({ method: "eth_estimateGas", params: [txRequest] });
    } catch (walletEstimateError) {
      const detail = walletEstimateError?.data?.message ||
        walletEstimateError?.message || rpcError?.message || "Gas estimation failed.";
      throw new Error(`MetaMask could not prepare the SOBYA Proof transaction: ${detail}`);
    }
  }
  if (typeof estimatedGas !== "string" || !/^0x[0-9a-f]+$/i.test(estimatedGas)) {
    throw new Error("The SOBYA RPC returned an invalid gas estimate. No transaction was sent.");
  }
  const gasLimit = (BigInt(estimatedGas) * 120n + 99n) / 100n;
  const txHash = await state.wallet.request({
    method: "eth_sendTransaction",
    params: [{ ...txRequest, gas: "0x" + gasLimit.toString(16) }]
  });
  $("tx-hash").value = txHash;
  const result = $("verify-result");
  message(result, `1 SOBY service fee submitted to ${SERVICE_WALLET}. Wait for confirmation, then verify your paid proof here. Transaction: ${txHash}`);
  result.classList.add("success");
  setWallet(`Proof submitted with 1 SOBY service fee: ${txHash}`);
}
async function verifyProof() {
  const txHash = $("tx-hash").value.trim();
  if (!isTransactionHash(txHash)) throw new Error("Enter a valid 32-byte transaction hash.");
  const [chain, tx, receipt] = await Promise.all([
    rpc("eth_chainId", []),
    rpc("eth_getTransactionByHash", [txHash]),
    rpc("eth_getTransactionReceipt", [txHash])
  ]);
  if (BigInt(chain) !== CHAIN_ID) throw new Error("The RPC endpoint is not connected to SOBYA Mainnet.");
  if (!tx) throw new Error("Transaction not found. It may still be pending or the hash may be incorrect.");
  if (!receipt) throw new Error("The transaction has not been confirmed yet.");
  if (receipt.status !== "0x1") throw new Error("The transaction failed on-chain.");
  const decoded = decodeProofPayload(tx.input || tx.data);
  if (!decoded || !isPaidProofRecord(tx, receipt, CHAIN_ID, SERVICE_WALLET, SERVICE_FEE_WEI)) {
    throw new Error("This transaction is not a valid paid SOBYA Proof record. It must send exactly 1 SOBY to the official Proof service wallet.");
  }
  const block = await rpc("eth_getBlockByNumber", [receipt.blockNumber, false]);
  const timestamp = block?.timestamp ? new Date(Number(BigInt(block.timestamp)) * 1000).toLocaleString(state.lang === "ar" ? "ar" : "en") : "Confirmed";
  let comparison = "Fingerprint recorded on-chain.";
  const selected = $("verify-file").files?.[0];
  if (selected) {
    const candidate = await fingerprint(selected);
    comparison = candidate.toLowerCase() === decoded.sha256.toLowerCase()
      ? "MATCH: the selected file has the same SHA-256 fingerprint."
      : "NO MATCH: the selected file differs from the registered fingerprint.";
  }
  const result = $("verify-result");
  result.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = "Valid SOBYA Proof record";
  const hash = document.createElement("code");
  hash.textContent = decoded.sha256;
  const details = document.createElement("p");
  details.textContent = `Signer: ${tx.from} · Block: ${BigInt(receipt.blockNumber).toString()} · ${timestamp}`;
  const match = document.createElement("p");
  match.textContent = comparison;
  const explorer = document.createElement("a");
  explorer.href = "https://explorer.nodesafe-app.xyz/sobya";
  explorer.target = "_blank";
  explorer.rel = "noopener";
  explorer.textContent = "Open SOBYA Explorer ↗";
  result.append(heading, hash, details, match, explorer);
  result.className = "result success";
  result.hidden = false;
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
$("verify-button").addEventListener("click", async () => {
  const button = $("verify-button");
  try {
    setBusy(button, true, state.lang === "ar" ? "جارٍ التحقق…" : "Verifying…");
    await verifyProof();
  } catch (error) { message($("verify-result"), error.message, "error"); }
  finally { setBusy(button, false); }
});
$("language").addEventListener("click", () => setLanguage(state.lang === "en" ? "ar" : "en"));
bindWalletEvents(findInjectedProvider());
