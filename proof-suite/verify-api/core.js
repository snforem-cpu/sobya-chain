const HASH_RE = /^0x[0-9a-fA-F]{64}$/;
const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

export const VERIFY_CONFIG = Object.freeze({
  chainId: 357812033857n,
  chainHex: "0x534f425941",
  registry: "0x9B1C6Cc504DEb8FA7aB9DAe499aB3D042fEC97b9",
  serviceWallet: "0xd316993423Fc6268038F4EE3EA7C0C5038513C18",
  feeWei: 1000000000000000000n,
  rpcUrls: Object.freeze([
    "https://sobya-evm-rpc.nodesafe-dapp.xyz",
    "https://sobya-evm-rpc.nodesafe-app.xyz"
  ])
});

export function isTransactionHash(value) {
  return typeof value === "string" && HASH_RE.test(value);
}

export function normalizeInvoiceMetadata(input = {}) {
  const clean = value => String(value ?? "").normalize("NFKC").trim().replace(/\s+/g, " ");
  const reference = clean(input.reference).toUpperCase();
  const issueDate = clean(input.issueDate);
  const amount = clean(input.amount);
  const currency = clean(input.currency).toUpperCase();
  const issuer = clean(input.issuer);
  const recipient = clean(input.recipient);
  if (!reference || reference.length > 120) throw new TypeError("Invoice reference must be 1–120 characters.");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(issueDate) || Number.isNaN(Date.parse(issueDate + "T00:00:00Z")) || new Date(issueDate + "T00:00:00Z").toISOString().slice(0, 10) !== issueDate) throw new TypeError("Enter a valid invoice issue date.");
  if (!/^(?:0|[1-9]\d*)(?:\.\d{1,6})?$/.test(amount) || amount.length > 24 || !Number.isFinite(Number(amount)) || Number(amount) <= 0) throw new TypeError("Enter a positive amount with up to 6 decimal places.");
  if (!/^[A-Z]{3}$/.test(currency)) throw new TypeError("Enter a three-letter currency code, such as USD or EUR.");
  if (issuer.length > 160 || recipient.length > 160) throw new TypeError("Issuer and recipient fields must be 160 characters or fewer.");
  return { version: 1, reference, issueDate, amount, currency, issuer, recipient };
}

export function canonicalInvoiceRecord(fileHash, metadata) {
  if (typeof fileHash !== "string" || !HASH_RE.test(fileHash)) throw new TypeError("A 32-byte SHA-256 file fingerprint is required.");
  const normalized = normalizeInvoiceMetadata(metadata);
  return JSON.stringify({
    domain: "SOBYA_INVOICE_PROOF",
    version: normalized.version,
    reference: normalized.reference,
    issueDate: normalized.issueDate,
    amount: normalized.amount,
    currency: normalized.currency,
    issuer: normalized.issuer,
    recipient: normalized.recipient,
    fileSha256: fileHash.toLowerCase()
  });
}

export async function sha256Hex(bytes, cryptoProvider = globalThis.crypto) {
  if (!cryptoProvider?.subtle) throw new Error("Web Crypto SHA-256 is unavailable.");
  const digest = await cryptoProvider.subtle.digest("SHA-256", bytes);
  return "0x" + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

export async function fingerprintFile(file, cryptoProvider = globalThis.crypto) {
  if (!file || typeof file.arrayBuffer !== "function") throw new TypeError("A File or Blob is required.");
  return sha256Hex(await file.arrayBuffer(), cryptoProvider);
}

export async function computeInvoiceProofHash(fileHash, metadata, cryptoProvider = globalThis.crypto) {
  return sha256Hex(new TextEncoder().encode(canonicalInvoiceRecord(fileHash, metadata)), cryptoProvider);
}

export function isValidRegistryRecord({ tx, receipt, decodedCall, recordedEvent, expectedChainId = VERIFY_CONFIG.chainId }) {
  if (!tx || !receipt || receipt.status !== "0x1") return false;
  if (!ADDRESS_RE.test(tx.from || "") || !ADDRESS_RE.test(tx.to || "")) return false;
  if (tx.to.toLowerCase() !== VERIFY_CONFIG.registry.toLowerCase()) return false;
  if (!decodedCall || decodedCall.name !== "recordProof" || !recordedEvent || recordedEvent.name !== "ProofRecorded") return false;
  try {
    if (BigInt(tx.value || "0x0") !== VERIFY_CONFIG.feeWei) return false;
    if (tx.chainId && BigInt(tx.chainId) !== BigInt(expectedChainId)) return false;
    const callHash = String(decodedCall.args?.[0] || "").toLowerCase();
    const submitter = String(recordedEvent.args?.[0] || "").toLowerCase();
    const eventHash = String(recordedEvent.args?.[1] || "").toLowerCase();
    if (!HASH_RE.test(callHash) || callHash === "0x" + "0".repeat(64)) return false;
    if (submitter !== tx.from.toLowerCase() || eventHash !== callHash) return false;
    return BigInt(recordedEvent.args?.[2] ?? 0) === VERIFY_CONFIG.feeWei;
  } catch {
    return false;
  }
}
