const HASH_RE = /^0x[0-9a-fA-F]{64}$/;
const TX_RE = /^0x[0-9a-fA-F]{64}$/;
const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

export function normalizeInvoiceMetadata(input) {
  const clean = value => String(value ?? "").normalize("NFKC").trim().replace(/\\s+/g, " ");
  const reference = clean(input.reference).toUpperCase();
  const issueDate = clean(input.issueDate);
  const amount = clean(input.amount);
  const currency = clean(input.currency).toUpperCase();
  const issuer = clean(input.issuer);
  const recipient = clean(input.recipient);
  if (!reference) throw new TypeError("Invoice reference is required.");
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(issueDate) || Number.isNaN(Date.parse(issueDate + "T00:00:00Z"))) throw new TypeError("Enter a valid invoice issue date.");
  if (!/^(?:0|[1-9]\\d*)(?:\\.\\d{1,6})?$/.test(amount)) throw new TypeError("Enter an amount using digits and an optional decimal point (up to 6 decimal places).");
  if (!/^[A-Z]{3}$/.test(currency)) throw new TypeError("Enter a three-letter currency code, such as USD or EUR.");
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

export async function computeInvoiceProofHash(fileHash, metadata, cryptoProvider = globalThis.crypto) {
  if (!cryptoProvider?.subtle) throw new Error("Web Crypto SHA-256 is unavailable in this browser.");
  const canonical = canonicalInvoiceRecord(fileHash, metadata);
  const bytes = new TextEncoder().encode(canonical);
  const digest = await cryptoProvider.subtle.digest("SHA-256", bytes);
  return "0x" + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function isTransactionHash(value) {
  return typeof value === "string" && TX_RE.test(value);
}

export function isValidRegistryRecord(tx, receipt, chainId, registryAddress, feeWei, call, event) {
  if (!tx || !receipt || receipt.status !== "0x1") return false;
  if (!ADDRESS_RE.test(tx.from || "") || !ADDRESS_RE.test(tx.to || "") || !ADDRESS_RE.test(registryAddress || "")) return false;
  if (tx.to.toLowerCase() !== registryAddress.toLowerCase()) return false;
  if (!call || call.name !== "recordProof" || !event || event.name !== "ProofRecorded") return false;
  try {
    if (BigInt(tx.value || "0x0") !== BigInt(feeWei)) return false;
    if (tx.chainId && BigInt(tx.chainId) !== BigInt(chainId)) return false;
    const callHash = String(call.args?.[0] || "").toLowerCase();
    const submitter = String(event.args?.[0] || "").toLowerCase();
    const eventHash = String(event.args?.[1] || "").toLowerCase();
    if (!HASH_RE.test(callHash) || callHash === "0x" + "0".repeat(64)) return false;
    return submitter === tx.from.toLowerCase() && eventHash === callHash && BigInt(event.args?.[2] ?? 0) === BigInt(feeWei);
  } catch { return false; }
}
