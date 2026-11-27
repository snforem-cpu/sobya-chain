const ID_RE = /^SOBYA-CERT-[0-9A-F]{32}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function clean(value) {
  return String(value ?? "").normalize("NFKC").trim().replace(/\s+/g, " ");
}

function validDate(value, optional = false) {
  if (optional && value === "") return true;
  return DATE_RE.test(value) &&
    !Number.isNaN(Date.parse(value + "T00:00:00Z")) &&
    new Date(value + "T00:00:00Z").toISOString().slice(0, 10) === value;
}

export function isCertificateId(value) {
  return typeof value === "string" && ID_RE.test(value);
}

export function generateCertificateId(cryptoProvider = globalThis.crypto) {
  if (!cryptoProvider?.getRandomValues) throw new Error("Secure random number generation is unavailable.");
  const bytes = new Uint8Array(16);
  cryptoProvider.getRandomValues(bytes);
  return "SOBYA-CERT-" + Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("").toUpperCase();
}

export function normalizeCertificate(input) {
  const certificateId = clean(input.certificateId).toUpperCase();
  const issuer = clean(input.issuer);
  const recipient = clean(input.recipient);
  const title = clean(input.title);
  const issueDate = clean(input.issueDate);
  const expiryDate = clean(input.expiryDate);
  const notes = clean(input.notes);

  if (!isCertificateId(certificateId)) throw new TypeError("A valid SOBYA certificate ID is required.");
  if (!issuer || issuer.length > 160) throw new TypeError("Issuer name must be 1–160 characters.");
  if (!recipient || recipient.length > 160) throw new TypeError("Recipient name must be 1–160 characters.");
  if (!title || title.length > 180) throw new TypeError("Certificate title must be 1–180 characters.");
  if (!validDate(issueDate)) throw new TypeError("Enter a valid issue date.");
  if (!validDate(expiryDate, true)) throw new TypeError("Enter a valid expiry date or leave it empty.");
  if (expiryDate && expiryDate < issueDate) throw new TypeError("Expiry date cannot be earlier than issue date.");
  if (notes.length > 1000) throw new TypeError("Additional details must be 1000 characters or fewer.");

  return { version: 1, certificateId, issuer, recipient, title, issueDate, expiryDate, notes };
}

export function canonicalCertificateRecord(input) {
  const normalized = normalizeCertificate(input);
  return JSON.stringify({
    domain: "SOBYA_CERTIFICATE_PROOF",
    version: normalized.version,
    certificateId: normalized.certificateId,
    issuer: normalized.issuer,
    recipient: normalized.recipient,
    title: normalized.title,
    issueDate: normalized.issueDate,
    expiryDate: normalized.expiryDate,
    notes: normalized.notes
  });
}

export async function computeCertificateHash(input, cryptoProvider = globalThis.crypto) {
  if (!cryptoProvider?.subtle) throw new Error("Web Crypto SHA-256 is unavailable in this browser.");
  const bytes = new TextEncoder().encode(canonicalCertificateRecord(input));
  const digest = await cryptoProvider.subtle.digest("SHA-256", bytes);
  return "0x" + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}
