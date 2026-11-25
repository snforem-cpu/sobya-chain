import { JsonRpcProvider, Wallet, Contract, getAddress } from "ethers";
import { AUTO_EXCHANGE_POLICY } from "./config.js";
import { applyConfirmedPriceChange } from "./pricing.js";
import { matchSobyReturn } from "./return-ledger.js";
import { executeReturnRefund, isReturnRefundEligible } from "./return-execution.js";

if (!(AUTO_EXCHANGE_POLICY.tradingEnabled && AUTO_EXCHANGE_POLICY.payoutEnabled)) {
  console.log("SOBY return/refund worker is safely disabled by project policy; no RPC or signing key was accessed.");
  process.exit(0);
}
const required = ["GH_TOKEN", "GH_REPOSITORY", "ETHEREUM_RPC_URL", "SOBYA_EVM_RPC_URL", "SOBYA_PAYOUT_PRIVATE_KEY"];
for (const name of required) if (!process.env[name]) throw new Error(name + " is required");
const api = "https://api.github.com/repos/" + process.env.GH_REPOSITORY;
const headers = { accept: "application/vnd.github+json", authorization: "Bearer " + process.env.GH_TOKEN,
  "x-github-api-version": "2022-11-28" };
async function gh(path, options = {}) {
  const response = await fetch(api + path, { ...options,
    headers: { ...headers, ...(options.body ? { "content-type": "application/json" } : {}) } });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error("GitHub API " + response.status + ": " + JSON.stringify(body));
  return body;
}
async function saveLedger(ledger, sha, message) {
  const content = Buffer.from(JSON.stringify(ledger, null, 2) + "\n").toString("base64");
  const result = await gh("/contents/auto-exchange/ledger.json", { method: "PUT",
    body: JSON.stringify({ message, content, sha, branch: "main" }) });
  return result.content.sha;
}
const raw = await gh("/contents/auto-exchange/ledger.json?ref=main");
let ledger = JSON.parse(Buffer.from(raw.content, "base64").toString("utf8"));
if (!Array.isArray(ledger.returnQuotes)) ledger.returnQuotes = [];
if (!Array.isArray(ledger.processedReturns)) ledger.processedReturns = [];
let ledgerSha = raw.sha;
const ethereum = new JsonRpcProvider(process.env.ETHEREUM_RPC_URL);
const sobya = new JsonRpcProvider(process.env.SOBYA_EVM_RPC_URL);
const [ethNetwork, sobyaNetwork] = await Promise.all([ethereum.getNetwork(), sobya.getNetwork()]);
if (Number(ethNetwork.chainId) !== AUTO_EXCHANGE_POLICY.ethereumChainId) throw new Error("Ethereum RPC chain ID mismatch");
if (Number(sobyaNetwork.chainId) !== AUTO_EXCHANGE_POLICY.sobyaEvmChainId) throw new Error("SOBYA EVM RPC chain ID mismatch");
const signer = new Wallet(process.env.SOBYA_PAYOUT_PRIVATE_KEY, ethereum);
const inventory = getAddress(AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress);
if (getAddress(signer.address) !== inventory) throw new Error("Refund signing key does not match configured inventory wallet");
const usdt = new Contract("0xdAC17F958D2ee523a2206206994597C13D831ec7",
  ["function balanceOf(address) view returns (uint256)", "function transfer(address,uint256) returns (bool)"], signer);
const requiredConfirmations = 2;
const head = await sobya.getBlockNumber();
const scanTo = head - (requiredConfirmations - 1);
const scanFrom = Math.max(0, Number(ledger.lastScannedSobyBlock ?? Math.max(0, scanTo - 100)) - 5);
if (scanTo >= scanFrom) {
  for (let height = scanFrom; height <= scanTo; height++) {
    const block = await sobya.getBlock(height, true);
    if (!block) continue;
    for (const tx of block.prefetchedTransactions) {
      if (!tx.to || getAddress(tx.to) !== inventory || tx.value <= 0n) continue;
      const transfer = { chainId: AUTO_EXCHANGE_POLICY.sobyaEvmChainId, txHash: tx.hash,
        from: tx.from, to: tx.to, amountAtomic: tx.value.toString(),
        blockNumber: height, blockTimestamp: new Date(Number(block.timestamp) * 1000).toISOString() };
      const matched = matchSobyReturn({ returnQuotes: ledger.returnQuotes,
        processedReturns: ledger.processedReturns, transfer, now: Date.now(),
        confirmations: head - height + 1, requiredConfirmations });
      if (matched.decision === "matched_returned_not_refunded") {
        ledger.returnQuotes = matched.returnQuotes;
        ledger.processedReturns = matched.processedReturns;
      }
    }
  }
  ledger.lastScannedSobyBlock = scanTo;
  ledgerSha = await saveLedger(ledger, ledgerSha, "Scan confirmed SOBY return deposits");
}
let completed = 0;
for (const quote of ledger.returnQuotes) {
  if (!isReturnRefundEligible(quote)) continue;
  const tx = await sobya.getTransaction(quote.returnTxHash);
  const receipt = await sobya.getTransactionReceipt(quote.returnTxHash);
  if (!tx || !receipt || receipt.status !== 1 ||
      getAddress(tx.from) !== getAddress(quote.sender) ||
      getAddress(tx.to) !== inventory || tx.value.toString() !== String(quote.paymentAmountAtomic)) continue;
  const result = await executeReturnRefund({ ledger, quote, ledgerSha,
    saveLedger, ethereum: {
      sobyaProvider: sobya,
      getFeeData: () => ethereum.getFeeData(),
      getBalance: address => ethereum.getBalance(address),
      getTransactionCount: (address, tag) => ethereum.getTransactionCount(address, tag)
    },
    usdt, signer, refundRecipient: getAddress(quote.sender),
    amount: BigInt(quote.payoutAmountAtomic), sobyaConfirmations: requiredConfirmations,
    ethereumConfirmations: 12, applyConfirmedPriceChange });
  ledger = result.ledger;
  ledgerSha = result.ledgerSha;
  if (result.completed) completed++;
}
console.log("SOBY return worker finished. Confirmed USDT refunds: " + completed + ".");
