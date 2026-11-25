import { calculateRequiredPayoutBalance } from "./payout-policy.js";
import { calculateNextPrice } from "./pricing.js";
import { AUTO_EXCHANGE_POLICY } from "./config.js";

export function isReturnRefundEligible(quote) {
  return (quote?.status === "returned" || quote?.status === "refund_waiting_funds") &&
    quote.refundTxHash === undefined && quote.refundNonce === undefined;
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
  if ((quote.status !== "returned" && quote.status !== "refund_waiting_funds") ||
      !/^0x[0-9a-fA-F]{40}$/.test(refundRecipient) ||
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

  // Reject a return size that would mathematically drive the agreed price to zero
  // before any USDT refund is broadcast.
  calculateNextPrice({
    currentPrice: ledger.currentPriceUsdtPerSoby ?? AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby,
    quantitySobyAtomic: quote.paymentAmountAtomic,
    direction: "down"
  });
  const balance = await usdt.balanceOf(signer.address);
  if (balance < amount) {
    quote.status = "refund_waiting_funds";
    quote.refundWaitReason = "Insufficient USDT inventory for quoted refund";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Hold USDT refund until inventory is funded " + quote.orderId);
    return { ledger, ledgerSha, completed: false, waitingForFunds: true };
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
    quote.status = "refund_waiting_funds";
    quote.refundWaitReason = "Insufficient ETH gas reserve for USDT refund";
    quote.requiredEthGasAtomic = requiredEth.toString();
    ledgerSha = await saveLedger(ledger, ledgerSha, "Hold USDT refund until ETH gas reserve is funded " + quote.orderId);
    return { ledger, ledgerSha, completed: false, waitingForFunds: true };
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
  const usdtAddress = "0xdAC17F958D2ee523a2206206994597C13D831ec7".toLowerCase();
  const transferConfirmed = (receipt.logs || []).some(log => {
    if (String(log.address).toLowerCase() !== usdtAddress) return false;
    try {
      const parsed = usdt.interface.parseLog(log);
      return parsed?.name === "Transfer" &&
        String(parsed.args.from).toLowerCase() === String(signer.address).toLowerCase() &&
        String(parsed.args.to).toLowerCase() === refundRecipient.toLowerCase() &&
        BigInt(parsed.args.value) === amount;
    } catch { return false; }
  });
  if (!transferConfirmed) {
    quote.status = "review";
    quote.refundReviewReason = "Successful Ethereum receipt did not contain the exact USDT Transfer event";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag USDT refund without matching Transfer event " + quote.orderId);
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
