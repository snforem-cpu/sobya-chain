import { JsonRpcProvider, Wallet, Interface, getAddress, id, zeroPadValue } from "ethers";
import { matchDeposit } from "./settlement.js";
import { AUTO_EXCHANGE_POLICY } from "./config.js";
import { applyConfirmedPriceChange } from "./pricing.js";
import { isPayoutEligible } from "./payout-policy.js";
import { executePayout } from "./payout-execution.js";

const enabled = AUTO_EXCHANGE_POLICY.buyTradingEnabled && AUTO_EXCHANGE_POLICY.buyPayoutEnabled;
if (!enabled) {
  console.log("USDT-to-SOBY payout worker is disabled by project policy; no RPC or signing key was accessed.");
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
const transferTopic = id("Transfer(address,address,uint256)");
const sobyaConfirmations = 2;
const requiredEthConfirmations = 12;
let completed = 0;

// Scan only confirmed Ethereum blocks. Re-scan a small overlap so a failed run
// cannot lose a boundary block; processedTransfers makes confirmed matches idempotent.
const ethHead = await eth.getBlockNumber();
const scanTo = ethHead - (requiredEthConfirmations - 1);
const scanFrom = Math.max(0, Number(ledger.lastScannedEthereumBlock ?? Math.max(0, scanTo - 100)) - 11);
if (scanTo >= scanFrom) {
  const logs = await eth.getLogs({
    address: usdtAddress,
    topics: [transferTopic, null, zeroPadValue(inventoryAddress, 32)],
    fromBlock: scanFrom,
    toBlock: scanTo
  });
  for (const log of logs) {
    const parsed = usdt.parseLog(log);
    const block = await eth.getBlock(log.blockNumber);
    const transfer = {
      chainId: AUTO_EXCHANGE_POLICY.ethereumChainId,
      txHash: log.transactionHash,
      logIndex: log.index,
      from: parsed.args.from,
      to: parsed.args.to,
      tokenAddress: log.address,
      amountAtomic: parsed.args.value.toString(),
      blockTimestamp: new Date(Number(block.timestamp) * 1000).toISOString()
    };
    const matched = matchDeposit({
      quotes: ledger.quotes,
      processedTransfers: ledger.processedTransfers || [],
      transfer,
      now: Date.now(),
      confirmations: ethHead - log.blockNumber + 1,
      requiredConfirmations: requiredEthConfirmations
    });
    if (matched.decision === "matched_paid_not_settled") {
      ledger.quotes = matched.quotes;
      ledger.processedTransfers = matched.processedTransfers;
      const paidQuote = ledger.quotes.find(q => q.orderId === matched.orderId);
      paidQuote.depositTxHash = transfer.txHash;
      paidQuote.depositLogIndex = transfer.logIndex;
      paidQuote.depositBlockNumber = log.blockNumber;
    }
  }
  ledger.lastScannedEthereumBlock = scanTo;
  ledgerSha = await saveLedger(ledger, ledgerSha, "Scan confirmed Ethereum USDT deposits for SOBYA Auto Exchange");
}

for (const quote of ledger.quotes) {
  if (!isPayoutEligible(quote)) continue;
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
  const payoutRecipient = getAddress(quote.sender);
  const result = await executePayout({
    ledger,
    quote,
    ledgerSha,
    saveLedger,
    sobya,
    signer,
    payoutRecipient,
    amount,
    sobyaConfirmations,
    applyConfirmedPriceChange: applyConfirmedPriceChange
  });
  ledger = result.ledger;
  ledgerSha = result.ledgerSha;
  if (result.completed) completed++;
}

console.log("Payout worker finished. Confirmed payouts: " + completed + ". Orders requiring manual reconciliation are not retried automatically.");
