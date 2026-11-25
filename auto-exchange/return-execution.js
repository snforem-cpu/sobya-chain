import { calculateRequiredPayoutBalance } from "./payout-policy.js";

export function isReturnRefundEligible(quote) {
  return quote?.status === "returned" && quote.refundTxHash === undefined && quote.refundNonce === undefined;
}

export async function executeReturnRefund({
  ledger, quote, ledgerSha, saveLedger, ethereum, usdt, signer,
  refundRecipient, amount, sobyaConfirmations = 2, ethereumConfirmations = 12,
  applyConfirmedPriceChange
}) {
  if (!isReturnRefundEligible(quote)) return { ledger, ledgerSha, completed: false, skipped: true };
  if (!ledger.returnQuotes?.some(item => item.orderId === quote.orderId && item === quote)) {
    throw new Error("Return quote must belong to the supplied ledger");
  }
  if (quote.status !== "returned" || !/^0x[0-9a-fA-F]{40}$/.test(refundRecipient) ||
      refundRecipient.toLowerCase() !== quote.sender.toLowerCase() ||
      amount <= 0n || amount.toString() !== String(quote.payoutAmountAtomic)) {
    throw new Error("USDT refund recipient or amount does not match the confirmed return quote");
  }
  if (!quote.returnTxHash || !Number.isSafeInteger(quote.returnBlockNumber) ||
      typeof saveLedger !== "function" || typeof applyConfirmedPriceChange !== "function") {
    throw new Error("confirmed SOBYA return and durable adapters are required");
  }
  const returnReceipt = await ethereum.sobyaProvider.getTransactionReceipt(quote.returnTxHash);
  if (!returnReceipt || returnReceipt.status !== 1) throw new Error("SOBYA return transaction is not confirmed successfully");
  const returnHead = await ethereum.sobyaProvider.getBlockNumber();
  if (returnHead - returnReceipt.blockNumber + 1 < sobyaConfirmations) throw new Error("SOBYA return confirmation threshold not reached");

  const balance = await usdt.balanceOf(signer.address);
  if (balance < amount) {
    quote.status = "review";
    quote.refundReviewReason = "Insufficient USDT inventory for quoted refund";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag USDT refund for insufficient inventory " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }
  const estimatedGas = await usdt.transfer.estimateGas(refundRecipient, amount);
  const gasLimit = (estimatedGas * 12_000n + 9_999n) / 10_000n;
  const feeData = await ethereum.getFeeData();
  let maxFeePerGas, feeOverrides;
  if (feeData.maxFeePerGas != null && feeData.maxPriorityFeePerGas != null) {
    maxFeePerGas = feeData.maxFeePerGas;
    feeOverrides = { maxFeePerGas: feeData.maxFeePerGas, maxPriorityFeePerGas: feeData.maxPriorityFeePerGas };
  } else if (feeData.gasPrice != null) {
    maxFeePerGas = feeData.gasPrice;
    feeOverrides = { gasPrice: feeData.gasPrice };
  } else throw new Error("Ethereum RPC did not provide usable gas fee data");
  const requiredEth = calculateRequiredPayoutBalance({
    payoutAmountAtomic: "1", gasLimit: gasLimit.toString(), maxFeePerGas: maxFeePerGas.toString()
  }) - 1n;
  const ethBalance = await ethereum.getBalance(signer.address);
  if (ethBalance < requiredEth) {
    quote.status = "review";
    quote.refundReviewReason = "Insufficient ETH gas reserve for USDT refund";
    quote.requiredEthGasAtomic = requiredEth.toString();
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag USDT refund for insufficient ETH gas " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }

  const nonce = await ethereum.getTransactionCount(signer.address, "pending");
  quote.refundNonce = nonce;
  quote.status = "refund_prepared";
  quote.refundPreparedAt = new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Reserve Ethereum nonce for USDT refund " + quote.orderId);

  const tx = await usdt.transfer(refundRecipient, amount, { nonce, gasLimit, ...feeOverrides });
  quote.refundTxHash = tx.hash;
  quote.status = "refund_broadcast";
  quote.refundBroadcastAt = new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Record USDT refund broadcast " + quote.orderId);

  const receipt = await tx.wait(ethereumConfirmations);
  if (receipt?.status !== 1) {
    quote.status = "review";
    quote.refundReviewReason = "Ethereum USDT refund transaction did not confirm successfully";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag USDT refund for review " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }
  ledger = applyConfirmedPriceChange({
    ledger, quantitySobyAtomic: quote.paymentAmountAtomic,
    direction: "down", settlementConfirmed: true
  });
  const settled = ledger.returnQuotes.find(item => item.orderId === quote.orderId);
  if (!settled) throw new Error("Settled return quote disappeared from ledger");
  settled.status = "settled";
  settled.refundedAt = new Date().toISOString();
  settled.refundBlockNumber = receipt.blockNumber;
  settled.refundGasUsed = receipt.gasUsed.toString();
  settled.refundFeePaidAtomic = (receipt.gasUsed * (receipt.gasPrice ?? maxFeePerGas)).toString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Confirm USDT refund and reduce SOBYA price for " + quote.orderId);
  return { ledger, ledgerSha, completed: true, review: false };
}
