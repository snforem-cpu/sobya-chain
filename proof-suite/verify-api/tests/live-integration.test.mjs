import test from "node:test";
import assert from "node:assert/strict";
import { Interface } from "ethers";
import { VERIFY_CONFIG } from "../core.js";

const txHash = "0x615604f8649ffd4f407e64e2eb14eb91a84720fd63d0dc4eaa17088647ed4206";
const rpcUrl = VERIFY_CONFIG.rpcUrls[0];
const abi = new Interface([
  "function recordProof(bytes32 documentHash) payable",
  "function feeRecipient() view returns (address)",
  "event ProofRecorded(address indexed submitter,bytes32 indexed documentHash,uint256 fee,uint256 timestamp)"
]);
async function rpc(method, params = []) {
  const response = await fetch(rpcUrl, { method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({jsonrpc:"2.0",id:1,method,params}), signal:AbortSignal.timeout(20000) });
  assert.equal(response.ok, true, method + " HTTP response");
  const body = await response.json();
  assert.equal(body.error, undefined, method + " RPC error");
  return body.result;
}
test("real Invoice Proof transaction is a valid paid SOBYA registry record", async () => {
  const [chainId, tx, receipt, code, recipientData] = await Promise.all([
    rpc("eth_chainId"), rpc("eth_getTransactionByHash",[txHash]),
    rpc("eth_getTransactionReceipt",[txHash]), rpc("eth_getCode",[VERIFY_CONFIG.registry,"latest"]),
    rpc("eth_call",[{to:VERIFY_CONFIG.registry,data:abi.encodeFunctionData("feeRecipient")},"latest"])
  ]);
  assert.equal(BigInt(chainId), VERIFY_CONFIG.chainId, "SOBYA chain ID");
  assert.ok(tx, "transaction exists on the live network");
  assert.ok(receipt, "transaction is confirmed");
  assert.equal(receipt.status, "0x1", "transaction succeeded");
  assert.equal(tx.to.toLowerCase(), VERIFY_CONFIG.registry.toLowerCase(), "registry destination");
  assert.equal(BigInt(tx.value), VERIFY_CONFIG.feeWei, "exact 1 SOBY service fee");
  assert.ok(code && code !== "0x", "registry contract is deployed");
  const recipient = abi.decodeFunctionResult("feeRecipient",recipientData)[0];
  assert.equal(recipient.toLowerCase(), VERIFY_CONFIG.serviceWallet.toLowerCase(), "official service fee recipient");
  const call = abi.parseTransaction({data:tx.input || tx.data,value:tx.value});
  assert.equal(call?.name,"recordProof","recordProof calldata");
  const logs = receipt.logs.filter(log => log.address.toLowerCase() === VERIFY_CONFIG.registry.toLowerCase());
  const parsed = logs.map(log => { try { return abi.parseLog({topics:log.topics,data:log.data}); } catch { return null; } }).find(log => log?.name === "ProofRecorded");
  assert.ok(parsed, "ProofRecorded event emitted by registry");
  assert.equal(parsed.args.submitter.toLowerCase(),tx.from.toLowerCase(),"event submitter matches signer");
  assert.equal(parsed.args.documentHash.toLowerCase(),call.args[0].toLowerCase(),"event fingerprint matches calldata");
  assert.equal(parsed.args.fee,VERIFY_CONFIG.feeWei,"event records exact 1 SOBY fee");
  console.log("LIVE INTEGRATION PASS", JSON.stringify({txHash,block:BigInt(receipt.blockNumber).toString(),signer:tx.from,fingerprint:call.args[0]}));
});
