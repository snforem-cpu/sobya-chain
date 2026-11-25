// Pure settlement matching core. No RPC access, signing, or payout is performed here.
// The caller must supply a durable, serialized ledger and enforce single-writer execution.
export function validateQuote(quote) {
  const required = ["orderId", "sender", "depositAddress", "tokenAddress", "chainId",
    "paymentAmountAtomic", "payoutAmountAtomic", "createdAt", "expiresAt", "status"];
  for (const key of required) {
    if (quote?.[key] === undefined || quote?.[key] === null || quote[key] === "") {
      throw new TypeError(`quote.${key} is required`);
    }
  }
  if (!/^0x[0-9a-fA-F]{40}$/.test(quote.sender) ||
      !/^0x[0-9a-fA-F]{40}$/.test(quote.depositAddress) ||
      !/^0x[0-9a-fA-F]{40}$/.test(quote.tokenAddress)) {
    throw new TypeError("quote contains an invalid EVM address");
  }
  if (!/^\d+$/.test(String(quote.paymentAmountAtomic)) ||
      !/^\d+$/.test(String(quote.payoutAmountAtomic)) ||
      BigInt(quote.paymentAmountAtomic) <= 0n || BigInt(quote.payoutAmountAtomic) <= 0n) {
    throw new TypeError("quote amounts must be positive integer atomic units");
  }
  if (!Number.isSafeInteger(quote.chainId) || quote.chainId <= 0) {
    throw new TypeError("quote.chainId must be a positive safe integer");
  }
  if (!Number.isFinite(Date.parse(quote.createdAt)) ||
      !Number.isFinite(Date.parse(quote.expiresAt)) ||
      Date.parse(quote.expiresAt) <= Date.parse(quote.createdAt)) {
    throw new TypeError("quote timestamps are invalid");
  }
  if (!["open", "paid", "review", "settled", "expired"].includes(quote.status)) {
    throw new TypeError("quote.status is invalid");
  }
  return true;
}

export function transferReplayKey(transfer) {
  if (!/^0x[0-9a-fA-F]{64}$/.test(transfer.txHash) ||
      !Number.isSafeInteger(transfer.logIndex) || transfer.logIndex < 0) {
    throw new TypeError("transfer requires txHash and non-negative logIndex");
  }
  return `${transfer.chainId}:${transfer.txHash.toLowerCase()}:${transfer.logIndex}`;
}

// Returns a decision and a NEW ledger. It never sends tokens or changes the input ledger.
// An exact payment amount is only a lookup key when a pre-existing unique quote ledger exists.
export function matchDeposit({ quotes, processedTransfers, transfer, now = Date.now(),
  confirmations, requiredConfirmations }) {
  if (!Array.isArray(quotes) || !Array.isArray(processedTransfers)) {
    throw new TypeError("quotes and processedTransfers must be arrays");
  }
  const replayKey = transferReplayKey(transfer);
  if (processedTransfers.includes(replayKey)) {
    return { decision: "duplicate", replayKey, quotes, processedTransfers };
  }
  if (!Number.isSafeInteger(requiredConfirmations) || requiredConfirmations < 1 ||
      !Number.isSafeInteger(confirmations) || confirmations < 0) {
    throw new TypeError("confirmation counts are invalid");
  }
  const base = { chainId: transfer.chainId,
    sender: transfer.from?.toLowerCase(),
    depositAddress: transfer.to?.toLowerCase(),
    tokenAddress: transfer.tokenAddress?.toLowerCase(),
    paymentAmountAtomic: String(transfer.amountAtomic) };
  const candidates = quotes.filter(q =>
    q.chainId === base.chainId &&
    q.sender.toLowerCase() === base.sender &&
    q.depositAddress.toLowerCase() === base.depositAddress &&
    q.tokenAddress.toLowerCase() === base.tokenAddress &&
    String(q.paymentAmountAtomic) === base.paymentAmountAtomic &&
    q.status === "open");
  if (candidates.length !== 1) {
    return { decision: candidates.length ? "ambiguous" : "unmatched",
      replayKey, quotes, processedTransfers };
  }
  const quote = candidates[0];
  if (Date.parse(transfer.blockTimestamp) < Date.parse(quote.createdAt) ||
      Date.parse(transfer.blockTimestamp) > Date.parse(quote.expiresAt) ||
      Date.parse(transfer.blockTimestamp) > now) {
    return { decision: "expired", replayKey, quotes, processedTransfers };
  }
  if (confirmations < requiredConfirmations) {
    return { decision: "confirmations_pending", replayKey, quotes, processedTransfers };
  }
  const nextQuotes = quotes.map(q => q.orderId === quote.orderId
    ? { ...q, status: "paid", depositTxHash: transfer.txHash, depositLogIndex: transfer.logIndex }
    : q);
  return { decision: "matched_paid_not_settled", replayKey,
    quotes: nextQuotes, processedTransfers: [...processedTransfers, replayKey],
    orderId: quote.orderId, payoutRecipient: quote.sender,
    payoutAmountAtomic: quote.payoutAmountAtomic };
}
