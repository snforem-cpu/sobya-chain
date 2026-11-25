import { readFile } from "node:fs/promises";
import { JsonRpcProvider, Wallet, Interface, getAddress } from "ethers";
import { AUTO_EXCHANGE_POLICY } from "./config.js";

const enabled = AUTO_EXCHANGE_POLICY.tradingEnabled && AUTO_EXCHANGE_POLICY.payoutEnabled;
if (!enabled) {
  console.log("Payout worker is safely disabled by project policy; no RPC or signing key was accessed.");
  process.exit(0);
}

const required = ["GH_TOKEN", "GH_REPOSITORY", "ETHEREUM_RPC_URL", "SOBYA_EVM_RPC_URL", "SOBYA_PAYOUT_PRIVATE_KEY"];
for (const name of required) if (!process.env[name]) throw new Error(name + " is required");
const repo = process.env.GH_REPOSITORY;
const api = "https://api.github.com/repos/" + repo;
const headers = {
  accept: "application/vnd.github+json",
  authorization: "Bearer " + process.env.GH_TOKEN,
  "x-github-api-version": "2022-11-28"
};
async function gh(path, options = {}) {
  const response = await fetch(api + path, {
    ...options,
    headers: { ...headers, ...(options.body ? { "content-type": "application/json" } : {}) }
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error("GitHub API " + response.status + ": " + JSON.stringify(body));
  return body;
}
async function saveLedger(ledger, sha, message) {
  const content = Buffer.from(JSON.stringify(ledger, null, 2) + "\n").toString("base64");
  const result = await gh("/contents/auto-exchange/ledger.json", {
    method: "PUT",
    body: JSON.stringify({ message, content, sha, branch: "main" })
  });
  return result.content.sha;
}

const ledgerFile = await gh("/contents/auto-exchange/ledger.json?ref=main");
let ledger = JSON.parse(Buffer.from(ledgerFile.content, "base64").toString("utf8"));
if (!Array.isArray(ledger.quotes)) throw new Error("Invalid quote ledger");
let ledgerSha = ledgerFile.sha;

const eth = new JsonRpcProvider(process.env.ETHEREUM_RPC_URL);
const sobya = new JsonRpcProvider(process.env.SOBYA_EVM_RPC_URL);
const ethNetwork = await eth.getNetwork();
const sobyaNetwork = await sobya.getNetwork();
if (Number(ethNetwork.chainId) !== AUTO_EXCHANGE_POLICY.ethereumChainId) throw new Error("Ethereum RPC chain ID mismatch");
if (Number(sobyaNetwork.chainId) !== AUTO_EXCHANGE_POLICY.sobyaEvmChainId) throw new Error("SOBYA EVM RPC chain ID mismatch");

const signer = new Wallet(process.env.SOBYA_PAYOUT_PRIVATE_KEY, sobya);
const inventoryAddress = getAddress(AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress);
if (getAddress(signer.address) !== inventoryAddress) throw new Error("Payout signing key does not match configured inventory wallet");
const usdtAddress = getAddress("0xdAC17F958D2ee523a2206206994597C13D831ec7");
const usdt = new Interface(["event Transfer(address indexed from,address indexed to,uint256 value)"]);
const sobyaConfirmations = 2;
let completed = 0;

for (const quote of ledger.quotes) {
  if (quote.status !== "paid" || quote.payoutTxHash || quote.payoutNonce !== undefined) continue;
  if (!quote.depositTxHash || !Number.isSafeInteger(quote.depositLogIndex) || quote.depositLogIndex < 0) continue;
  if (quote.chainId !== AUTO_EXCHANGE_POLICY.ethereumChainId ||
      getAddress(quote.depositAddress) !== inventoryAddress ||
      getAddress(quote.tokenAddress) !== usdtAddress ||
      !/^0x[0-9a-fA-F]{40}$/.test(quote.sender) ||
      !/^\d+$/.test(String(quote.paymentAmountAtomic)) ||
      !/^\d+$/.test(String(quote.payoutAmountAtomic))) {
    quote.status = "review";
    quote.payoutReviewReason = "Quote fields failed payout policy validation";
    continue;
  }

  const receipt = await eth.getTransactionReceipt(quote.depositTxHash);
  if (!receipt || receipt.status !== 1) continue;
  const currentEthBlock = await eth.getBlockNumber();
  if (currentEthBlock - receipt.blockNumber + 1 < 12) continue;
  const block = await eth.getBlock(receipt.blockNumber);
  const minedAt = Number(block.timestamp) * 1000;
  if (minedAt < Date.parse(quote.createdAt) || minedAt > Date.parse(quote.expiresAt)) {
    quote.status = "review";
    quote.payoutReviewReason = "USDT deposit was mined outside quote validity";
    continue;
  }
  const log = receipt.logs.find(item => item.index === quote.depositLogIndex);
  if (!log || getAddress(log.address) !== usdtAddress) continue;
  let parsed;
  try { parsed = usdt.parseLog(log); } catch { continue; }
  if (getAddress(parsed.args.from) !== getAddress(quote.sender) ||
      getAddress(parsed.args.to) !== inventoryAddress ||
      parsed.args.value.toString() !== String(quote.paymentAmountAtomic)) continue;

  const amount = BigInt(quote.payoutAmountAtomic);
  const balance = await sobya.getBalance(signer.address);
  if (balance < amount) {
    quote.status = "review";
    quote.payoutReviewReason = "Insufficient SOBYA native balance for payout";
    continue;
  }

  // Reserve the sender nonce in the durable ledger before broadcasting.
  // If a run is interrupted after this point, the worker will not blindly
  // create a second payout; the order is held for reconciliation.
  const nonce = await sobya.getTransactionCount(signer.address, "pending");
  quote.payoutNonce = nonce;
  quote.status = "payout_prepared";
  quote.payoutPreparedAt = new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Reserve SOBYA payout nonce for " + quote.orderId);

  const tx = await signer.sendTransaction({ to: getAddress(quote.sender), value: amount, nonce });
  quote.payoutTxHash = tx.hash;
  quote.status = "payout_broadcast";
  quote.payoutBroadcastAt = new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Record SOBYA payout broadcast for " + quote.orderId);

  const payoutReceipt = await tx.wait(sobyaConfirmations);
  if (payoutReceipt?.status === 1) {
    quote.status = "settled";
    quote.settledAt = new Date().toISOString();
    quote.payoutBlockNumber = payoutReceipt.blockNumber;
    ledgerSha = await saveLedger(ledger, ledgerSha, "Confirm SOBYA payout for " + quote.orderId);
    completed++;
  } else {
    quote.status = "review";
    quote.payoutReviewReason = "SOBYA payout transaction did not confirm successfully";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag SOBYA payout for review " + quote.orderId);
  }
}

console.log("Payout worker finished. Confirmed payouts: " + completed + ". Orders requiring manual reconciliation are not retried automatically.");
