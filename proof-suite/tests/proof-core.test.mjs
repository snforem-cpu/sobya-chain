import test from "node:test";
import assert from "node:assert/strict";
import { encodeProofPayload, decodeProofPayload, isTransactionHash, isPaidProofRecord, isContractProofRecord } from "../proof-core.js";

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

test("accepts only successful 1 SOBY payments to the service wallet carrying a proof payload", () => {
  const serviceWallet = "0xd316993423Fc6268038F4EE3EA7C0C5038513C18";
  const fee = 1000000000000000000n;
  const tx = {
    from: account, to: serviceWallet, value: "0xde0b6b3a7640000",
    input: encodeProofPayload(sampleHash), chainId: "0x534f425941"
  };
  const receipt = { status: "0x1" };
  assert.equal(isPaidProofRecord(tx, receipt, 357812033857n, serviceWallet, fee), true);
  assert.equal(isPaidProofRecord({ ...tx, value: "0x0" }, receipt, 357812033857n, serviceWallet, fee), false);
  assert.equal(isPaidProofRecord({ ...tx, value: "0x1" }, receipt, 357812033857n, serviceWallet, fee), false);
  assert.equal(isPaidProofRecord({ ...tx, to: account }, receipt, 357812033857n, serviceWallet, fee), false);
  assert.equal(isPaidProofRecord({ ...tx, to: "0x" + "34".repeat(20) }, receipt, 357812033857n, serviceWallet, fee), false);
  assert.equal(isPaidProofRecord(tx, { status: "0x0" }, 357812033857n, serviceWallet, fee), false);
  assert.equal(isPaidProofRecord({ ...tx, chainId: "0x1" }, receipt, 357812033857n, serviceWallet, fee), false);
});


test("accepts only a successful registry call with the matching ProofRecorded event and exact fee", () => {
  const registry = "0x" + "56".repeat(20);
  const fee = 1000000000000000000n;
  const tx = { from: account, to: registry, value: "0xde0b6b3a7640000", chainId: "0x534f425941" };
  const receipt = { status: "0x1" };
  const call = { name: "recordProof", args: [sampleHash] };
  const event = { name: "ProofRecorded", args: [account, sampleHash, fee, 123n] };
  assert.equal(isContractProofRecord(tx, receipt, 357812033857n, registry, fee, call, event), true);
  assert.equal(isContractProofRecord({ ...tx, to: account }, receipt, 357812033857n, registry, fee, call, event), false);
  assert.equal(isContractProofRecord(tx, { status: "0x0" }, 357812033857n, registry, fee, call, event), false);
  assert.equal(isContractProofRecord(tx, receipt, 357812033857n, registry, fee, call, { ...event, args: [account, "0x" + "cd".repeat(32), fee, 123n] }), false);
  assert.equal(isContractProofRecord(tx, receipt, 357812033857n, registry, fee, call, { ...event, args: [account, sampleHash, 1n, 123n] }), false);
  assert.equal(isContractProofRecord(tx, receipt, 357812033857n, registry, fee, { name: "transfer", args: [sampleHash] }, event), false);
});
