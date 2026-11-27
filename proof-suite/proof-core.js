const MARKER = new TextEncoder().encode("SOBYA_PROOF");
const VERSION = 1;
const DOCUMENT_TYPE = 1;
const PAYLOAD_LENGTH = MARKER.length + 2 + 32;

function hexToBytes(value) {
  if (typeof value !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(value)) {
    throw new TypeError("A 32-byte SHA-256 hash is required.");
  }
  const clean = value.slice(2);
  return Uint8Array.from(clean.match(/.{2}/g), byte => Number.parseInt(byte, 16));
}

function bytesToHex(bytes) {
  return "0x" + Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

export function encodeProofPayload(hash, type = DOCUMENT_TYPE) {
  if (type !== DOCUMENT_TYPE) throw new TypeError("Unsupported proof type.");
  const digest = hexToBytes(hash);
  const payload = new Uint8Array(PAYLOAD_LENGTH);
  payload.set(MARKER, 0);
  payload[MARKER.length] = VERSION;
  payload[MARKER.length + 1] = type;
  payload.set(digest, MARKER.length + 2);
  return bytesToHex(payload);
}

export function decodeProofPayload(data) {
  if (typeof data !== "string" || !/^0x(?:[0-9a-fA-F]{2})+$/.test(data)) return null;
  const bytes = Uint8Array.from(data.slice(2).match(/.{2}/g), byte => Number.parseInt(byte, 16));
  if (bytes.length !== PAYLOAD_LENGTH) return null;
  for (let i = 0; i < MARKER.length; i += 1) if (bytes[i] !== MARKER[i]) return null;
  if (bytes[MARKER.length] !== VERSION || bytes[MARKER.length + 1] !== DOCUMENT_TYPE) return null;
  return { version: VERSION, type: "document", sha256: bytesToHex(bytes.slice(MARKER.length + 2)) };
}

export function isTransactionHash(value) {
  return typeof value === "string" && /^0x[0-9a-fA-F]{64}$/.test(value);
}

export function isPaidProofRecord(tx, receipt, expectedChainId, serviceWallet, serviceFeeWei) {
  if (!tx || !receipt || receipt.status !== "0x1") return false;
  if (!/^0x[0-9a-fA-F]{40}$/.test(tx.from || "") || !/^0x[0-9a-fA-F]{40}$/.test(tx.to || "")) return false;
  if (typeof serviceWallet !== "string" || !/^0x[0-9a-fA-F]{40}$/.test(serviceWallet)) return false;
  if (tx.to.toLowerCase() !== serviceWallet.toLowerCase()) return false;
  try {
    if (BigInt(tx.value || "0x0") !== BigInt(serviceFeeWei)) return false;
    if (tx.chainId && BigInt(tx.chainId) !== BigInt(expectedChainId)) return false;
  } catch {
    return false;
  }
  return decodeProofPayload(tx.input || tx.data) !== null;
}


export function isContractProofRecord(tx, receipt, expectedChainId, registryAddress, serviceFeeWei, decodedCall, recordedEvent) {
  if (!tx || !receipt || receipt.status !== "0x1") return false;
  if (!/^0x[0-9a-fA-F]{40}$/.test(tx.from || "") || !/^0x[0-9a-fA-F]{40}$/.test(tx.to || "")) return false;
  if (typeof registryAddress !== "string" || !/^0x[0-9a-fA-F]{40}$/.test(registryAddress)) return false;
  if (tx.to.toLowerCase() !== registryAddress.toLowerCase()) return false;
  if (!decodedCall || decodedCall.name !== "recordProof" || !recordedEvent || recordedEvent.name !== "ProofRecorded") return false;
  try {
    if (BigInt(tx.value || "0x0") !== BigInt(serviceFeeWei)) return false;
    if (tx.chainId && BigInt(tx.chainId) !== BigInt(expectedChainId)) return false;
    const callHash = String(decodedCall.args?.[0] || "").toLowerCase();
    const eventSubmitter = String(recordedEvent.args?.[0] || "").toLowerCase();
    const eventHash = String(recordedEvent.args?.[1] || "").toLowerCase();
    const eventFee = BigInt(recordedEvent.args?.[2] ?? 0);
    if (!/^0x[0-9a-f]{64}$/.test(callHash) || callHash === "0x" + "0".repeat(64)) return false;
    if (eventSubmitter !== tx.from.toLowerCase() || eventHash !== callHash) return false;
    if (eventFee !== BigInt(serviceFeeWei)) return false;
    return true;
  } catch { return false; }
}
