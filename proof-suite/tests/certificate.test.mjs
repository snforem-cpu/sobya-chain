import test from "node:test";
import assert from "node:assert/strict";
import { canonicalCertificateRecord, computeCertificateHash, generateCertificateId, isCertificateId, normalizeCertificate } from "../certificate/core.js";

const base = {
  certificateId: "SOBYA-CERT-" + "A1".repeat(16),
  issuer: " SOBYA Academy ",
  recipient: "  Test   Recipient ",
  title: "Blockchain Fundamentals",
  issueDate: "2026-11-27",
  expiryDate: "",
  notes: "Completed successfully"
};

test("normalizes certificate metadata and produces a domain-separated canonical record", () => {
  const record = JSON.parse(canonicalCertificateRecord(base));
  assert.equal(record.domain, "SOBYA_CERTIFICATE_PROOF");
  assert.equal(record.version, 1);
  assert.equal(record.issuer, "SOBYA Academy");
  assert.equal(record.recipient, "Test Recipient");
  assert.equal(record.certificateId, base.certificateId);
});

test("rejects invalid certificate IDs, dates, and expiry before issue date", () => {
  assert.equal(isCertificateId(base.certificateId), true);
  assert.equal(isCertificateId("SOBYA-CERT-123"), false);
  assert.throws(() => normalizeCertificate({ ...base, certificateId: "invalid" }), TypeError);
  assert.throws(() => normalizeCertificate({ ...base, issueDate: "2026-02-30" }), TypeError);
  assert.throws(() => normalizeCertificate({ ...base, expiryDate: "2026-01-01" }), TypeError);
});

test("certificate hashes are deterministic and change when any bound field changes", async () => {
  const first = await computeCertificateHash(base);
  assert.match(first, /^0x[0-9a-f]{64}$/);
  assert.equal(await computeCertificateHash(base), first);
  assert.notEqual(await computeCertificateHash({ ...base, recipient: "Different Recipient" }), first);
  assert.notEqual(await computeCertificateHash({ ...base, certificateId: "SOBYA-CERT-" + "B2".repeat(16) }), first);
});

test("generates a 128-bit random certificate identifier", () => {
  const deterministicCrypto = { getRandomValues(bytes) { bytes.fill(0xab); return bytes; } };
  const id = generateCertificateId(deterministicCrypto);
  assert.equal(id, "SOBYA-CERT-" + "AB".repeat(16));
  assert.equal(isCertificateId(id), true);
});
