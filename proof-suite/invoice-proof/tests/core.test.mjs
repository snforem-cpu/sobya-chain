import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { normalizeInvoiceMetadata, canonicalInvoiceRecord, computeInvoiceProofHash, isTransactionHash, isValidRegistryRecord } from "../core.js";

const fileHash = "0x" + "ab".repeat(32);
const invoice = { reference:" inv-2026-0042 ", issueDate:"2026-11-27", amount:"1250.50", currency:"usd", issuer:"SOBYA Trading", recipient:"Client A" };

test("normalizes invoice metadata deterministically", () => {
  const normalized = normalizeInvoiceMetadata(invoice);
  assert.equal(normalized.reference, "INV-2026-0042");
  assert.equal(normalized.currency, "USD");
  assert.equal(normalized.amount, "1250.50");
  assert.equal(normalizeInvoiceMetadata({...invoice, reference:"INV-2026-0042", currency:"USD"}).reference, normalized.reference);
});

test("rejects missing or malformed invoice fields", () => {
  assert.throws(() => normalizeInvoiceMetadata({...invoice, reference:""}), /reference/i);
  assert.throws(() => normalizeInvoiceMetadata({...invoice, issueDate:"27-11-2026"}), /date/i);
  assert.throws(() => normalizeInvoiceMetadata({...invoice, issueDate:"2026-02-31"}), /date/i);
  assert.throws(() => normalizeInvoiceMetadata({...invoice, amount:"1,250.50"}), /amount/i);
  assert.throws(() => normalizeInvoiceMetadata({...invoice, amount:"0"}), /amount/i);
  assert.throws(() => normalizeInvoiceMetadata({...invoice, currency:"US"}), /currency/i);
  assert.throws(() => canonicalInvoiceRecord("0x1234", invoice), /SHA-256/i);
});

test("invoice proof binds the document fingerprint and private invoice metadata", async () => {
  const a = await computeInvoiceProofHash(fileHash, invoice, webcrypto);
  const b = await computeInvoiceProofHash(fileHash, {...invoice, reference:"INV-2026-0042", currency:"USD"}, webcrypto);
  const changedFile = await computeInvoiceProofHash("0x" + "cd".repeat(32), invoice, webcrypto);
  const changedAmount = await computeInvoiceProofHash(fileHash, {...invoice, amount:"1251.50"}, webcrypto);
  assert.equal(a, b);
  assert.notEqual(a, changedFile);
  assert.notEqual(a, changedAmount);
  assert.match(a, /^0x[0-9a-f]{64}$/);
});

test("accepts only a successful 1 SOBY registry record with matching event", () => {
  const account = "0x" + "12".repeat(20);
  const registry = "0x" + "56".repeat(20);
  const fee = 1000000000000000000n;
  const hash = "0x" + "ab".repeat(32);
  const tx = {from:account,to:registry,value:"0xde0b6b3a7640000",chainId:"0x534f425941"};
  const receipt = {status:"0x1"};
  const call = {name:"recordProof",args:[hash]};
  const event = {name:"ProofRecorded",args:[account,hash,fee,123n]};
  assert.equal(isValidRegistryRecord(tx,receipt,357812033857n,registry,fee,call,event),true);
  assert.equal(isValidRegistryRecord({...tx,value:"0x0"},receipt,357812033857n,registry,fee,call,event),false);
  assert.equal(isValidRegistryRecord(tx,{status:"0x0"},357812033857n,registry,fee,call,event),false);
  assert.equal(isValidRegistryRecord(tx,receipt,357812033857n,registry,fee,call,{...event,args:[account,"0x"+"cd".repeat(32),fee,123n]}),false);
});

test("recognizes transaction hashes", () => {
  assert.equal(isTransactionHash("0x" + "01".repeat(32)), true);
  assert.equal(isTransactionHash("0x1234"), false);
});
