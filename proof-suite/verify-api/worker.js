import { Interface } from "ethers";
import {
  VERIFY_CONFIG, isTransactionHash, isValidRegistryRecord,
  computeInvoiceProofHash
} from "./core.js";

const abi = new Interface([
  "function recordProof(bytes32 documentHash) payable",
  "function feeRecipient() view returns (address)",
  "event ProofRecorded(address indexed submitter,bytes32 indexed documentHash,uint256 fee,uint256 timestamp)"
]);
const encoder = new TextEncoder();
const MAX_BODY = 16_384;

function response(data, status = 200, origin = "*") {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": origin,
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "content-type",
      "vary": "Origin"
    }
  });
}
function fail(message, status = 400, origin = "*") {
  return response({ ok: false, error: { message } }, status, origin);
}
function validHash(value) {
  return typeof value === "string" && /^0x[0-9a-f]{64}$/i.test(value);
}

async function verifyRecord(txHash, expectedFingerprint, env) {
  if (!isTransactionHash(txHash)) throw new Error("Provide a valid 32-byte transaction hash.");
  const urls = [env.SOBYA_RPC_URL || VERIFY_CONFIG.rpcUrls[0], VERIFY_CONFIG.rpcUrls[1]];
  let lastError;
  async function rpc(method, params = []) {
    for (const url of urls) {
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
          signal: AbortSignal.timeout(12000)
        });
        if (!res.ok) throw new Error("RPC HTTP " + res.status);
        const body = await res.json();
        if (body.error) throw new Error(body.error.message || "RPC request failed.");
        if (!Object.prototype.hasOwnProperty.call(body, "result")) throw new Error("Malformed RPC response.");
        return body.result;
      } catch (error) { lastError = error; }
    }
    throw new Error("SOBYA Mainnet RPC unavailable: " + (lastError?.message || "unknown error"));
  }

  const [chainId, tx, receipt, code, feeData] = await Promise.all([
    rpc("eth_chainId"),
    rpc("eth_getTransactionByHash", [txHash]),
    rpc("eth_getTransactionReceipt", [txHash]),
    rpc("eth_getCode", [VERIFY_CONFIG.registry, "latest"]),
    rpc("eth_call", [{ to: VERIFY_CONFIG.registry, data: abi.encodeFunctionData("feeRecipient") }, "latest"])
  ]);
  if (BigInt(chainId) !== VERIFY_CONFIG.chainId) throw new Error("RPC endpoint is not connected to SOBYA Mainnet.");
  if (!tx) throw new Error("Transaction not found.");
  if (!receipt) throw new Error("Transaction is not confirmed yet.");
  if (receipt.status !== "0x1") throw new Error("Transaction failed on-chain.");
  if (!code || code === "0x") throw new Error("SOBYA Proof Registry contract is unavailable.");
  const feeRecipient = String(abi.decodeFunctionResult("feeRecipient", feeData)[0]);
  if (feeRecipient.toLowerCase() !== VERIFY_CONFIG.serviceWallet.toLowerCase()) throw new Error("Registry service wallet mismatch.");

  let call = null;
  try {
    const parsed = abi.parseTransaction({ data: tx.input || tx.data, value: tx.value });
    if (parsed) call = { name: parsed.name, args: [...parsed.args] };
  } catch {}
  let event = null;
  for (const log of receipt.logs || []) {
    if (log.address?.toLowerCase() !== VERIFY_CONFIG.registry.toLowerCase()) continue;
    try {
      const parsed = abi.parseLog({ topics: log.topics, data: log.data });
      if (parsed?.name === "ProofRecorded") {
        event = { name: parsed.name, args: [parsed.args.submitter, parsed.args.documentHash, parsed.args.fee, parsed.args.timestamp] };
        break;
      }
    } catch {}
  }
  if (!isValidRegistryRecord({ tx, receipt, decodedCall: call, recordedEvent: event, feeRecipient })) {
    throw new Error("Transaction is not a valid SOBYA Proof Registry record.");
  }
  const fingerprint = String(call.args[0]).toLowerCase();
  const block = await rpc("eth_getBlockByNumber", [receipt.blockNumber, false]);
  return {
    valid: true,
    match: expectedFingerprint ? fingerprint === expectedFingerprint.toLowerCase() : null,
    type: "proof",
    txHash,
    fingerprint,
    signer: tx.from,
    blockNumber: BigInt(receipt.blockNumber).toString(),
    timestamp: block?.timestamp ? new Date(Number(BigInt(block.timestamp)) * 1000).toISOString() : null,
    chainId: VERIFY_CONFIG.chainId.toString(),
    registry: VERIFY_CONFIG.registry,
    feeRecipient
  };
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "*";
    if (request.method === "OPTIONS") return response({}, 204, origin);
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/v1/health") {
      return response({ ok: true, service: "SOBYA Verify API", network: "SOBYA Mainnet", chainId: VERIFY_CONFIG.chainId.toString(), readOnly: true }, 200, origin);
    }
    if (request.method !== "POST" || !["/v1/verify/proof", "/v1/verify/invoice"].includes(url.pathname)) {
      return fail("Route not found. See /v1/health and the API documentation.", 404, origin);
    }
    const length = Number(request.headers.get("content-length") || 0);
    if (length > MAX_BODY) return fail("Request body is too large.", 413, origin);
    let body;
    try {
      const raw = await request.text();
      if (encoder.encode(raw).byteLength > MAX_BODY) return fail("Request body is too large.", 413, origin);
      body = JSON.parse(raw);
    } catch { return fail("Request body must be valid JSON.", 400, origin); }
    try {
      let expected = null;
      if (url.pathname.endsWith("/invoice")) {
        if (!validHash(body.fileHash)) throw new Error("fileHash must be a SHA-256 hex fingerprint.");
        expected = await computeInvoiceProofHash(body.fileHash, body.metadata);
      } else if (body.fileHash !== undefined) {
        if (!validHash(body.fileHash)) throw new Error("fileHash must be a SHA-256 hex fingerprint.");
        expected = body.fileHash.toLowerCase();
      }
      const result = await verifyRecord(body.txHash, expected, env);
      if (url.pathname.endsWith("/invoice")) result.type = "invoice";
      result.match = expected ? result.match : null;
      return response({ ok: true, result }, 200, origin);
    } catch (error) {
      const message = error?.message || "Verification failed.";
      const status = /not found/i.test(message) ? 404 : /not confirmed/i.test(message) ? 409 : /RPC unavailable/i.test(message) ? 503 : 422;
      return fail(message, status, origin);
    }
  }
};
