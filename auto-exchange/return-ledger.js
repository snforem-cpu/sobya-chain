import { AUTO_EXCHANGE_POLICY } from "./config.js";
import { parsePriceAtomic } from "./pricing.js";

const SOBY_SCALE = 10n ** 18n;
const USDT_SCALE = 10n ** 6n;
const MAX_UNIQUE_TAIL = 1_000_000n;

export function parseSobyAtomic(value) {
  const s = String(value ?? "").trim();
  if (!/^\d+(?:\.\d{1,18})?$/.test(s)) throw new TypeError("SOBY amount must have up to 18 decimal places");
  const [whole, fraction = ""] = s.split(".");
  const amount = BigInt(whole) * SOBY_SCALE + BigInt((fraction + "0".repeat(18)).slice(0, 18));
  if (amount <= 0n) throw new TypeError("SOBY amount must be greater than zero");
  return amount;
}
export function formatSobyAtomic(value) {
  const n = BigInt(value);
  return String(n / SOBY_SCALE) + "." + String(n % SOBY_SCALE).padStart(18, "0").replace(/0+$/, "");
}
export function formatUsdtAtomic(value) {
  const n = BigInt(value);
  return String(n / USDT_SCALE) + "." + String(n % USDT_SCALE).padStart(6, "0");
}
export function calculateUsdtRefundAtomic({ sobyAmountAtomic, priceUsdtPerSoby, feeBps = AUTO_EXCHANGE_POLICY.exchangeFeeBps }) {
  const amount = BigInt(sobyAmountAtomic);
  if (amount <= 0n || !Number.isSafeInteger(feeBps) || feeBps < 0 || feeBps >= 10_000) {
    throw new TypeError("invalid SOBY amount or fee");
  }
  const price = parsePriceAtomic(priceUsdtPerSoby);
  return amount * price * USDT_SCALE * BigInt(10_000 - feeBps) /
    (SOBY_SCALE * SOBY_SCALE * 10_000n);
}
export function allocateUniqueReturnAmount(requestedAmountAtomic, returnQuotes) {
  const used = new Set(returnQuotes.map(q => String(q.paymentAmountAtomic)));
  const requested = BigInt(requestedAmountAtomic);
  for (let tail = 1n; tail <= MAX_UNIQUE_TAIL; tail++) {
    const candidate = requested + tail;
    if (!used.has(candidate.toString())) {
      return { paymentAmountAtomic: candidate.toString(), markerAtomic: tail.toString() };
    }
  }
  throw new Error("No unique SOBY atomic amount remains for this requested base amount");
}
export function createReturnQuote({ ledger, issueNumber, sender, requestedAmount, now = new Date() }) {
  if (!ledger || !Array.isArray(ledger.returnQuotes)) throw new TypeError("ledger.returnQuotes must be an array");
  if (!Number.isSafeInteger(issueNumber) || issueNumber < 1) throw new TypeError("invalid return request issue number");
  if (!/^0x[0-9a-fA-F]{40}$/.test(sender)) throw new TypeError("invalid EVM sender address");
  const existing = ledger.returnQuotes.find(q => q.requestIssueNumber === issueNumber);
  if (existing) return { ledger, existing };
  const requestedAmountAtomic = parseSobyAtomic(requestedAmount);
  const allocated = allocateUniqueReturnAmount(requestedAmountAtomic, ledger.returnQuotes);
  const created = new Date(now);
  if (!Number.isFinite(created.getTime())) throw new TypeError("invalid quote creation time");
  const expires = new Date(created.getTime() + AUTO_EXCHANGE_POLICY.quoteValiditySeconds * 1000);
  const quotedPrice = String(ledger.currentPriceUsdtPerSoby ?? AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby);
  const payoutAmountAtomic = calculateUsdtRefundAtomic({
    sobyAmountAtomic: allocated.paymentAmountAtomic,
    priceUsdtPerSoby: quotedPrice
  });
  if (payoutAmountAtomic <= 0n) throw new RangeError("return quote is too small to produce a positive USDT refund");
  const quote = {
    orderId: "SOBYA-RETURN-" + created.toISOString().replace(/[-:.TZ]/g, "") + "-" + issueNumber,
    requestIssueNumber: issueNumber,
    sender: sender.toLowerCase(),
    depositAddress: AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress.toLowerCase(),
    chainId: AUTO_EXCHANGE_POLICY.sobyaEvmChainId,
    requestedAmountAtomic: requestedAmountAtomic.toString(),
    paymentAmountAtomic: allocated.paymentAmountAtomic,
    uniqueMarkerAtomic: allocated.markerAtomic,
    payoutAmountAtomic: payoutAmountAtomic.toString(),
    quotedPrice,
    exchangeFeeBps: AUTO_EXCHANGE_POLICY.exchangeFeeBps,
    createdAt: created.toISOString(),
    expiresAt: expires.toISOString(),
    status: "open"
  };
  return { ledger: { ...ledger, returnQuotes: [...ledger.returnQuotes, quote] }, quote };
}
export function parseReturnIssueBody(body = "") {
  const sender = body.match(/###\s*(?:EVM wallet address|Wallet address)\s*\r?\n+([^\r\n]+)/i)?.[1]?.trim();
  const amount = body.match(/###\s*(?:SOBY amount to return|SOBY amount)\s*\r?\n+([^\r\n]+)/i)?.[1]?.trim();
  if (!sender || !amount) throw new TypeError("Complete both wallet address and SOBY return amount fields");
  return { sender, requestedAmount: amount };
}
export function returnReplayKey(transfer) {
  if (!/^0x[0-9a-fA-F]{64}$/.test(transfer.txHash)) throw new TypeError("return transfer requires a transaction hash");
  return String(transfer.chainId) + ":" + transfer.txHash.toLowerCase();
}
export function matchSobyReturn({ returnQuotes, processedReturns, transfer, now = Date.now(), confirmations, requiredConfirmations }) {
  if (!Array.isArray(returnQuotes) || !Array.isArray(processedReturns)) throw new TypeError("return quote and replay collections must be arrays");
  if (!Number.isSafeInteger(transfer.chainId) || transfer.chainId !== AUTO_EXCHANGE_POLICY.sobyaEvmChainId ||
      !/^0x[0-9a-fA-F]{40}$/.test(transfer.from || "") ||
      !/^0x[0-9a-fA-F]{40}$/.test(transfer.to || "") ||
      !/^\d+$/.test(String(transfer.amountAtomic)) || BigInt(transfer.amountAtomic) <= 0n ||
      !Number.isFinite(Date.parse(transfer.blockTimestamp))) throw new TypeError("SOBYA return transfer fields are invalid");
  const replayKey = returnReplayKey(transfer);
  if (processedReturns.includes(replayKey)) return { decision: "duplicate", replayKey, returnQuotes, processedReturns };
  if (!Number.isSafeInteger(requiredConfirmations) || requiredConfirmations < 1 ||
      !Number.isSafeInteger(confirmations) || confirmations < 0) throw new TypeError("invalid confirmation counts");
  const candidates = returnQuotes.filter(q =>
    q.status === "open" &&
    q.chainId === transfer.chainId &&
    q.sender.toLowerCase() === transfer.from.toLowerCase() &&
    q.depositAddress.toLowerCase() === transfer.to.toLowerCase() &&
    String(q.paymentAmountAtomic) === String(transfer.amountAtomic));
  if (candidates.length !== 1) return { decision: candidates.length ? "ambiguous" : "unmatched", replayKey, returnQuotes, processedReturns };
  const quote = candidates[0];
  const minedAt = Date.parse(transfer.blockTimestamp);
  if (minedAt < Date.parse(quote.createdAt) || minedAt > Date.parse(quote.expiresAt) || minedAt > now) {
    return { decision: "expired", replayKey, returnQuotes, processedReturns };
  }
  if (confirmations < requiredConfirmations) return { decision: "confirmations_pending", replayKey, returnQuotes, processedReturns };
  const nextQuotes = returnQuotes.map(q => q.orderId === quote.orderId
    ? { ...q, status: "returned", returnTxHash: transfer.txHash, returnBlockNumber: transfer.blockNumber }
    : q);
  return { decision: "matched_returned_not_refunded", replayKey, returnQuotes: nextQuotes,
    processedReturns: [...processedReturns, replayKey], orderId: quote.orderId };
}
