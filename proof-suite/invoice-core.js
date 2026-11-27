const HASH_RE = /^0x[0-9a-fA-F]{64}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const AMOUNT_RE = /^(?:0|[1-9]\d*)(?:\.\d{1,6})?$/;

export function normalizeInvoiceMetadata(input) {
  const invoiceRef = String(input?.invoiceRef ?? "").trim();
  const issueDate = String(input?.issueDate ?? "").trim();
  const currency = String(input?.currency ?? "").trim().toUpperCase();
  const amount = String(input?.amount ?? "").trim();
  if (!invoiceRef || invoiceRef.length > 120) throw new TypeError("Enter an invoice reference (1–120 characters).");
  if (!DATE_RE.test(issueDate)) throw new TypeError("Enter a valid invoice date in YYYY-MM-DD format.");
  const parsedDate = new Date(issueDate + "T00:00:00Z");
  if (Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== issueDate) throw new TypeError("Enter a valid invoice date in YYYY-MM-DD format.");
  if (!/^[A-Z]{3}$/.test(currency)) throw new TypeError("Enter a three-letter currency code, such as USD.");
  if (!AMOUNT_RE.test(amount) || amount.length > 24 || Number(amount) <= 0 || !Number.isFinite(Number(amount))) throw new TypeError("Enter a positive amount with up to 6 decimal places (maximum 24 characters).");
  return { invoiceRef, issueDate, currency, amount };
}

export function canonicalInvoiceRecord(fileHash, metadata) {
  if (typeof fileHash !== "string" || !HASH_RE.test(fileHash)) throw new TypeError("A 32-byte invoice file SHA-256 fingerprint is required.");
  const normalized = normalizeInvoiceMetadata(metadata);
  return JSON.stringify({
    domain: "SOBYA_INVOICE_PROOF",
    version: 1,
    invoiceRef: normalized.invoiceRef,
    issueDate: normalized.issueDate,
    currency: normalized.currency,
    amount: normalized.amount,
    fileSha256: fileHash.toLowerCase()
  });
}

export async function invoiceRecordHash(fileHash, metadata, cryptoProvider = globalThis.crypto) {
  if (!cryptoProvider?.subtle) throw new Error("Web Crypto SHA-256 is unavailable in this browser.");
  const bytes = new TextEncoder().encode(canonicalInvoiceRecord(fileHash, metadata));
  const digest = await cryptoProvider.subtle.digest("SHA-256", bytes);
  return "0x" + Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
}
