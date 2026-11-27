import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { canonicalInvoiceRecord, normalizeInvoiceMetadata, computeInvoiceProofHash } from "../invoice-core.js";

const fileHash = "0x" + "ab".repeat(32);
const meta = { reference:" INV-2026-01 ", issueDate:"2026-11-27", currency:"usd", amount:"1250.00", issuer:"Supplier Ltd", recipient:"Customer Ltd" };

test("normalizes invoice metadata and creates a deterministic canonical record", () => {
  const value = canonicalInvoiceRecord(fileHash, meta);
  assert.match(value, /"reference":"INV-2026-01"/);
  assert.match(value, /"currency":"USD"/);
  assert.equal(value, canonicalInvoiceRecord(fileHash, {...meta, reference:"INV-2026-01", currency:"USD"}));
});

test("rejects incomplete or malformed invoice metadata", () => {
  assert.throws(() => normalizeInvoiceMetadata({...meta, reference:""}), TypeError);
  assert.throws(() => normalizeInvoiceMetadata({...meta, issueDate:"27/11/2026"}), TypeError);
  assert.throws(() => normalizeInvoiceMetadata({...meta, issueDate:"2026-02-30"}), TypeError);
  assert.throws(() => normalizeInvoiceMetadata({...meta, currency:"US"}), TypeError);
  assert.throws(() => normalizeInvoiceMetadata({...meta, amount:"-1"}), TypeError);
  assert.throws(() => normalizeInvoiceMetadata({...meta, amount:"0"}), TypeError);
  assert.throws(() => canonicalInvoiceRecord("0x1234", meta), TypeError);
});

test("hash changes when file or invoice metadata changes", async () => {
  const a = await computeInvoiceProofHash(fileHash, meta, webcrypto);
  const b = await computeInvoiceProofHash(fileHash, {...meta, amount:"1251.00"}, webcrypto);
  const c = await computeInvoiceProofHash("0x" + "cd".repeat(32), meta, webcrypto);
  const d = await computeInvoiceProofHash(fileHash, {...meta, issuer:"Other supplier"}, webcrypto);
  assert.match(a, /^0x[0-9a-f]{64}$/);
  assert.notEqual(a, b);
  assert.notEqual(a, c);
  assert.notEqual(a, d);
});
