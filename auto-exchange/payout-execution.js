import { isPayoutEligible } from "./payout-policy.js";
import { validateQuote } from "./settlement.js";

// Executes one already-verified, confirmed deposit payout. All external effects are
// injected so the exact production lifecycle can be exercised with deterministic mocks.
export async function executePayout({
  ledger,
  quote,
  ledgerSha,
  saveLedger,
  sobya,
  signer,
  payoutRecipient,
  amount,
  sobyaConfirmations = 2,
  applyConfirmedPriceChange
}) {
  if (!isPayoutEligible(quote)) {
    return { ledger, ledgerSha, completed: false, skipped: true };
  }
  if (!ledger.quotes.some(item => item.orderId === quote.orderId && item === quote)) {
    throw new Error("Payout quote must belong to the supplied ledger");
  }
  validateQuote(quote);
  if (quote.status !== "paid" && quote.status !== "payout_waiting_funds") {
    throw new Error("Only a paid deposit quote may be paid out");
  }
  if (!/^0x[0-9a-fA-F]{40}$/.test(payoutRecipient) ||
      payoutRecipient.toLowerCase() !== quote.sender.toLowerCase()) {
    throw new Error("Payout recipient must exactly match the quote sender");
  }
  if (amount <= 0n || amount.toString() !== String(quote.payoutAmountAtomic)) {
    throw new Error("Payout amount must exactly match the quoted atomic SOBY amount");
  }
  if (typeof saveLedger !== "function" || typeof applyConfirmedPriceChange !== "function") {
    throw new TypeError("persistence and confirmed-price adapters are required");
  }

  const estimatedGas = await sobya.estimateGas({
    to: payoutRecipient, value: amount, from: signer.address
  });
  const gasLimit = (estimatedGas * 12_000n + 9_999n) / 10_000n;
  const feeData = await sobya.getFeeData();
  let maxFeePerGas;
  let feeOverrides;
  if (feeData.maxFeePerGas != null && feeData.maxPriorityFeePerGas != null) {
    maxFeePerGas = feeData.maxFeePerGas;
    feeOverrides = {
      maxFeePerGas: feeData.maxFeePerGas,
      maxPriorityFeePerGas: feeData.maxPriorityFeePerGas
    };
  } else if (feeData.gasPrice != null) {
    maxFeePerGas = feeData.gasPrice;
    feeOverrides = { gasPrice: feeData.gasPrice };
  } else {
    throw new Error("SOBYA RPC did not provide usable gas fee data");
  }

  const networkFeeBudget = gasLimit * maxFeePerGas;
  const netPayoutAmount = amount - networkFeeBudget;
  if (netPayoutAmount <= 0n) throw new Error("SOBYA network fee exceeds the quoted payout; manual review required");
  // The gross quote is split between the customer's net SOBY and the SOBYA network fee.
  const requiredBalance = amount;
  const balance = await sobya.getBalance(signer.address);
  if (balance < requiredBalance) {
    quote.status = "payout_waiting_funds";
    quote.payoutWaitReason = "Insufficient SOBY balance for payout plus estimated gas reserve";
    quote.requiredNativeBalanceAtomic = requiredBalance.toString();
    ledgerSha = await saveLedger(ledger, ledgerSha, "Hold SOBYA payout until inventory is funded " + quote.orderId);
    return { ledger, ledgerSha, completed: false, waitingForFunds: true };
  }

  // Persist the nonce reservation before any broadcast. A crash from here onward
  // leaves a non-eligible order, which must be reconciled rather than re-signed.
  const nonce = await sobya.getTransactionCount(signer.address, "pending");
  quote.payoutNonce = nonce;
  quote.status = "payout_prepared";
  quote.payoutPreparedAt = new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Reserve SOBYA payout nonce for " + quote.orderId);

  const tx = await signer.sendTransaction({
    to: payoutRecipient, value: netPayoutAmount, nonce, gasLimit, ...feeOverrides
  });
  quote.payoutTxHash = tx.hash;
  quote.status = "payout_broadcast";
  quote.payoutBroadcastAt = new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Record SOBYA payout broadcast for " + quote.orderId);

  const payoutReceipt = await tx.wait(sobyaConfirmations);
  if (payoutReceipt?.status !== 1) {
    quote.status = "review";
    quote.payoutReviewReason = "SOBYA payout transaction did not confirm successfully";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag SOBYA payout for review " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }

  ledger = applyConfirmedPriceChange({
    ledger,
    quantitySobyAtomic: netPayoutAmount.toString(),
    direction: "up",
    settlementConfirmed: true
  });
  const settledQuote = ledger.quotes.find(item => item.orderId === quote.orderId);
  if (!settledQuote) throw new Error("Settled quote disappeared from ledger");
  settledQuote.status = "settled";
  settledQuote.settledAt = new Date().toISOString();
  settledQuote.payoutBlockNumber = payoutReceipt.blockNumber;
  settledQuote.payoutGasUsed = payoutReceipt.gasUsed.toString();
  settledQuote.payoutGrossAmountAtomic = amount.toString();
  settledQuote.payoutNetworkFeeBudgetAtomic = networkFeeBudget.toString();
  settledQuote.payoutNetAmountAtomic = netPayoutAmount.toString();
  settledQuote.payoutFeePaidAtomic =
    (payoutReceipt.gasUsed * (payoutReceipt.gasPrice ?? maxFeePerGas)).toString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Confirm SOBYA payout and update price for " + quote.orderId);
  return { ledger, ledgerSha, completed: true, review: false };
}
