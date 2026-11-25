import { AUTO_EXCHANGE_POLICY } from "./config.js";

export const ETHEREUM_USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7";
const USDT_SCALE = 1_000_000n;
const SOBY_SCALE = 10n ** 18n;

export function parseUsdtAtomic(value) {
  const s = String(value ?? "").trim();
  if (!/^\d+(?:\.\d{1,6})?$/.test(s)) throw new TypeError("USDT amount must have up to 6 decimal places");
  const [whole, fraction = ""] = s.split(".");
  const amount = BigInt(whole) * USDT_SCALE + BigInt((fraction + "000000").slice(0, 6));
  if (amount <= 0n) throw new TypeError("USDT amount must be greater than zero");
  return amount;
}
export function formatUsdtAtomic(value) {
  const n = BigInt(value);
  return String(n / USDT_SCALE) + "." + String(n % USDT_SCALE).padStart(6, "0");
}
export function calculateOpeningQuote(paymentAmountAtomic) {
  const payment = BigInt(paymentAmountAtomic);
  if (payment <= 0n) throw new TypeError("payment amount must be positive");
  // At the agreed opening price: SOBY = USDT / 0.005, less the 1% fee.
  return payment * SOBY_SCALE * 1000n * BigInt(10_000 - AUTO_EXCHANGE_POLICY.exchangeFeeBps) /
    (USDT_SCALE * 5n * 10_000n);
}
export function allocateUniquePaymentAmount(requestedAmountAtomic, quotes) {
  const used = new Set(quotes.map(q => String(q.paymentAmountAtomic)));
  const requested = BigInt(requestedAmountAtomic);
  // The unique micro-USDT tail is part of the quoted total, not a separate fee.
  for (let suffix = 1n; suffix <= 999_999n; suffix++) {
    const candidate = requested + suffix;
    if (!used.has(candidate.toString())) return { paymentAmountAtomic: candidate.toString(), markerAtomic: suffix.toString() };
  }
  throw new Error("No unique USDT micro-amount remains for this requested base amount");
}
export function createQuote({ ledger, issueNumber, sender, requestedAmount, now = new Date() }) {
  if (!ledger || !Array.isArray(ledger.quotes)) throw new TypeError("ledger.quotes must be an array");
  if (!Number.isSafeInteger(issueNumber) || issueNumber < 1) throw new TypeError("invalid request issue number");
  if (!/^0x[0-9a-fA-F]{40}$/.test(sender)) throw new TypeError("invalid EVM sender address");
  const existing = ledger.quotes.find(q => q.requestIssueNumber === issueNumber);
  if (existing) return { ledger, existing };
  const requestedAmountAtomic = parseUsdtAtomic(requestedAmount);
  const allocated = allocateUniquePaymentAmount(requestedAmountAtomic, ledger.quotes);
  const created = new Date(now);
  if (!Number.isFinite(created.getTime())) throw new TypeError("invalid quote creation time");
  const expires = new Date(created.getTime() + AUTO_EXCHANGE_POLICY.quoteValiditySeconds * 1000);
  const quote = {
    orderId: "SOBYA-" + created.toISOString().replace(/[-:.TZ]/g, "") + "-" + issueNumber,
    requestIssueNumber: issueNumber,
    sender: sender.toLowerCase(),
    depositAddress: AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress.toLowerCase(),
    tokenAddress: ETHEREUM_USDT.toLowerCase(),
    chainId: AUTO_EXCHANGE_POLICY.ethereumChainId,
    requestedAmountAtomic: requestedAmountAtomic.toString(),
    paymentAmountAtomic: allocated.paymentAmountAtomic,
    uniqueMarkerAtomic: allocated.markerAtomic,
    payoutAmountAtomic: calculateOpeningQuote(allocated.paymentAmountAtomic).toString(),
    quotedPrice: "0.005",
    exchangeFeeBps: AUTO_EXCHANGE_POLICY.exchangeFeeBps,
    createdAt: created.toISOString(),
    expiresAt: expires.toISOString(),
    status: "open"
  };
  return { ledger: { ...ledger, quotes: [...ledger.quotes, quote] }, quote };
}
export function parseQuoteIssueBody(body = "") {
  const sender = body.match(/###\s*(?:EVM wallet address|Wallet address)\s*\r?\n+([^\r\n]+)/i)?.[1]?.trim();
  const amount = body.match(/###\s*(?:Requested USDT amount|USDT amount)\s*\r?\n+([^\r\n]+)/i)?.[1]?.trim();
  if (!sender || !amount) throw new TypeError("Complete both wallet address and requested USDT amount fields");
  return { sender, requestedAmount: amount };
}
