import { Interface } from "https://esm.sh/ethers@6.13.5";
import {
  VERIFY_CONFIG, isTransactionHash, isValidRegistryRecord,
  fingerprintFile, computeInvoiceProofHash
} from "./core.js";

const registryInterface = new Interface([
  "function recordProof(bytes32 documentHash) payable",
  "function feeRecipient() view returns (address)",
  "event ProofRecorded(address indexed submitter,bytes32 indexed documentHash,uint256 fee,uint256 timestamp)"
]);

function normalizeRpcUrls(urls) {
  const list = Array.isArray(urls) && urls.length ? urls : VERIFY_CONFIG.rpcUrls;
  if (list.some(url => typeof url !== "string" || !/^https:\/\//i.test(url))) {
    throw new TypeError("RPC URLs must be HTTPS endpoints.");
  }
  return [...new Set(list)];
}

export function createSobyaVerifyClient({ rpcUrls, fetchImpl = globalThis.fetch, cryptoProvider = globalThis.crypto } = {}) {
  if (typeof fetchImpl !== "function") throw new TypeError("A Fetch-compatible implementation is required.");
  const endpoints = normalizeRpcUrls(rpcUrls);
  let requestId = 0;

  async function rpc(method, params = []) {
    let lastError;
    for (const url of endpoints) {
      try {
        const response = await fetchImpl(url, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ jsonrpc: "2.0", id: ++requestId, method, params })
        });
        if (!response.ok) throw new Error("RPC HTTP " + response.status);
        const body = await response.json();
        if (body.error) throw new Error(body.error.message || "SOBYA RPC request failed.");
        if (!Object.prototype.hasOwnProperty.call(body, "result")) throw new Error("Malformed JSON-RPC response.");
        return body.result;
      } catch (error) {
        lastError = error;
      }
    }
    throw new Error("All SOBYA RPC endpoints failed: " + (lastError?.message || "unknown error"));
  }

  async function verifyRecord(txHash, expectedFingerprint = null) {
    if (!isTransactionHash(txHash)) throw new TypeError("A valid 32-byte transaction hash is required.");
    const [chainId, tx, receipt, registryCode, feeRecipientData] = await Promise.all([
      rpc("eth_chainId"),
      rpc("eth_getTransactionByHash", [txHash]),
      rpc("eth_getTransactionReceipt", [txHash]),
      rpc("eth_getCode", [VERIFY_CONFIG.registry, "latest"]),
      rpc("eth_call", [{ to: VERIFY_CONFIG.registry, data: registryInterface.encodeFunctionData("feeRecipient") }, "latest"])
    ]);
    if (BigInt(chainId) !== VERIFY_CONFIG.chainId) throw new Error("RPC endpoint is not connected to SOBYA Mainnet.");
    if (!tx) throw new Error("Transaction not found.");
    if (!receipt) throw new Error("Transaction is not confirmed yet.");
    if (receipt.status !== "0x1") throw new Error("Transaction failed on-chain.");
    if (!registryCode || registryCode === "0x") throw new Error("The configured SOBYA Proof Registry contract is unavailable.");
    const feeRecipient = String(registryInterface.decodeFunctionResult("feeRecipient", feeRecipientData)[0]);
    if (feeRecipient.toLowerCase() !== VERIFY_CONFIG.serviceWallet.toLowerCase()) throw new Error("The registry fee recipient does not match the official SOBYA service wallet.");
    let decodedCall = null;
    try {
      const parsed = registryInterface.parseTransaction({ data: tx.input || tx.data, value: tx.value });
      if (parsed) decodedCall = { name: parsed.name, args: [...parsed.args] };
    } catch {}
    let recordedEvent = null;
    for (const log of receipt.logs || []) {
      if (log.address?.toLowerCase() !== VERIFY_CONFIG.registry.toLowerCase()) continue;
      try {
        const parsed = registryInterface.parseLog({ topics: log.topics, data: log.data });
        if (parsed?.name === "ProofRecorded") {
          recordedEvent = { name: parsed.name, args: [parsed.args.submitter, parsed.args.documentHash, parsed.args.fee, parsed.args.timestamp] };
          break;
        }
      } catch {}
    }
    if (!isValidRegistryRecord({ tx, receipt, decodedCall, recordedEvent, feeRecipient })) {
      throw new Error("Transaction is not a valid SOBYA Proof Registry record.");
    }
    const fingerprint = String(decodedCall.args[0]).toLowerCase();
    if (expectedFingerprint && fingerprint !== expectedFingerprint.toLowerCase()) {
      return {
        valid: true, match: false, type: "proof", txHash,
        fingerprint, signer: tx.from, blockNumber: BigInt(receipt.blockNumber).toString()
      };
    }
    const block = await rpc("eth_getBlockByNumber", [receipt.blockNumber, false]);
    return {
      valid: true, match: expectedFingerprint ? true : null, type: "proof", txHash,
      fingerprint, signer: tx.from, blockNumber: BigInt(receipt.blockNumber).toString(),
      timestamp: block?.timestamp ? new Date(Number(BigInt(block.timestamp)) * 1000).toISOString() : null,
      chainId: VERIFY_CONFIG.chainId.toString(), registry: VERIFY_CONFIG.registry
    };
  }

  return Object.freeze({
    async verifyProof({ txHash, file } = {}) {
      const expected = file ? await fingerprintFile(file, cryptoProvider) : null;
      const result = await verifyRecord(txHash, expected);
      if (file && result.match === false) result.message = "The selected file does not match the registered fingerprint.";
      if (file && result.match === true) result.message = "The selected file matches the registered fingerprint.";
      return result;
    },
    async verifyInvoiceProof({ txHash, file, metadata } = {}) {
      if (!file) throw new TypeError("The original invoice file is required.");
      const fileHash = await fingerprintFile(file, cryptoProvider);
      const expected = await computeInvoiceProofHash(fileHash, metadata, cryptoProvider);
      const result = await verifyRecord(txHash, expected);
      result.type = "invoice";
      result.message = result.match
        ? "The invoice file and supplied metadata match the registered fingerprint."
        : "The invoice file or supplied metadata do not match the registered fingerprint.";
      return result;
    }
  });
}
