import test from "node:test";
import assert from "node:assert/strict";
import { encodeProofPayload, decodeProofPayload, isTransactionHash, isSuccessfulSelfRecord } from "../proof-core.js";

const sampleHash = "0x" + "ab".repeat(32);
const account = "0x" + "12".repeat(20);

test("encodes and decodes a document fingerprint", () => {
  const payload = encodeProofPayload(sampleHash);
  const decoded = decodeProofPayload(payload);
  assert.equal(decoded.version, 1);
  assert.equal(decoded.type, "document");
  assert.equal(decoded.sha256, sampleHash);
});

test("rejects malformed hashes and unsupported record types", () => {
  assert.throws(() => encodeProofPayload("0x1234"), TypeError);
  assert.throws(() => encodeProofPayload(sampleHash, 2), TypeError);
  assert.equal(decodeProofPayload("0x1234"), null);
});

test("recognizes transaction hashes only in 32-byte hex form", () => {
  assert.equal(isTransactionHash("0x" + "01".repeat(32)), true);
  assert.equal(isTransactionHash("0x1234"), false);
});

test("accepts only successful self-transactions carrying a valid proof payload", () => {
  const tx = { from: account, to: account, input: encodeProofPayload(sampleHash), chainId: "0x534f425941" };
  const receipt = { status: "0x1" };
  assert.equal(isSuccessfulSelfRecord(tx, receipt, 357812033857n), true);
  assert.equal(isSuccessfulSelfRecord({ ...tx, to: "0x" + "34".repeat(20) }, receipt, 357812033857n), false);
  assert.equal(isSuccessfulSelfRecord(tx, { status: "0x0" }, 357812033857n), false);
  assert.equal(isSuccessfulSelfRecord({ ...tx, chainId: "0x1" }, receipt, 357812033857n), false);
});
