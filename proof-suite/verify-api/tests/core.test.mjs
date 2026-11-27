import test from "node:test";
import assert from "node:assert/strict";
import {
  VERIFY_CONFIG, isTransactionHash, normalizeInvoiceMetadata,
  canonicalInvoiceRecord, isValidRegistryRecord
} from "../core.js";

const hash = "0x" + "a".repeat(64);
const signer = "0x" + "1".repeat(40);

test("prefers the current SOBYA Mainnet RPC endpoint", () => {
  assert.equal(VERIFY_CONFIG.rpcUrls[0], "https://sobya-evm-rpc.nodesafe-app.xyz");
});

test("accepts only 32-byte transaction hashes", () => {
  assert.equal(isTransactionHash(hash), true);
  assert.equal(isTransactionHash("0x1234"), false);
  assert.equal(isTransactionHash(null), false);
});

test("normalizes invoice metadata consistently", () => {
  const value = normalizeInvoiceMetadata({
    reference: " inv-7 ", issueDate: "2026-11-27", amount: "125.50",
    currency: "usd", issuer: "  ACME   Ltd ", recipient: " Buyer "
  });
  assert.deepEqual(value, {
    version: 1, reference: "INV-7", issueDate: "2026-11-27",
    amount: "125.50", currency: "USD", issuer: "ACME Ltd", recipient: "Buyer"
  });
});

test("rejects invalid invoice fields", () => {
  assert.throws(() => normalizeInvoiceMetadata({ reference: "", issueDate: "2026-02-30", amount: "0", currency: "US" }));
  assert.throws(() => normalizeInvoiceMetadata({ reference: "A", issueDate: "2026-11-27", amount: "-1", currency: "USD" }));
});

test("canonical invoice fingerprint input is domain separated and stable", () => {
  const first = canonicalInvoiceRecord(hash, {
    reference: "inv-7", issueDate: "2026-11-27", amount: "125.50",
    currency: "usd", issuer: "ACME", recipient: "Buyer"
  });
  const second = canonicalInvoiceRecord(hash.toUpperCase().replace("0X", "0x"), {
    reference: "INV-7", issueDate: "2026-11-27", amount: "125.50",
    currency: "USD", issuer: "ACME", recipient: "Buyer"
  });
  assert.equal(first, second);
  assert.match(first, /SOBYA_INVOICE_PROOF/);
});

function validRecord(overrides = {}) {
  const tx = { from: signer, to: VERIFY_CONFIG.registry, value: "0x" + VERIFY_CONFIG.feeWei.toString(16), chainId: VERIFY_CONFIG.chainId.toString() };
  const receipt = { status: "0x1" };
  const decodedCall = { name: "recordProof", args: [hash] };
  const recordedEvent = { name: "ProofRecorded", args: [signer, hash, VERIFY_CONFIG.feeWei, 1n] };
  return { tx, receipt, decodedCall, recordedEvent, feeRecipient: VERIFY_CONFIG.serviceWallet, ...overrides };
}

test("accepts a valid paid registry record", () => {
  assert.equal(isValidRegistryRecord(validRecord()), true);
});

test("rejects failed, unpaid, wrong-contract and mismatched-event records", () => {
  assert.equal(isValidRegistryRecord(validRecord({ receipt: { status: "0x0" } })), false);
  assert.equal(isValidRegistryRecord(validRecord({ tx: { ...validRecord().tx, value: "0x0" } })), false);
  assert.equal(isValidRegistryRecord(validRecord({ tx: { ...validRecord().tx, to: signer } })), false);
  assert.equal(isValidRegistryRecord(validRecord({ recordedEvent: { name: "ProofRecorded", args: [signer, "0x" + "b".repeat(64), VERIFY_CONFIG.feeWei, 1n] } })), false);
  assert.equal(isValidRegistryRecord(validRecord({ recordedEvent: { name: "ProofRecorded", args: [signer, hash, 0n, 1n] } })), false);
  assert.equal(isValidRegistryRecord(validRecord({ feeRecipient: signer })), false);
});
