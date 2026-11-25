import { calculateRequiredPayoutBalance } from "./payout-policy.js";
import { calculateNextPrice } from "./pricing.js";
import { AUTO_EXCHANGE_POLICY } from "./config.js";

const ETH_SCALE = 10n ** 18n;
const USD_SCALE = 10n ** 8n;
const USDT_SCALE = 10n ** 6n;

export function calculateUsdtNetworkFeeAtomic({ gasLimit, maxFeePerGas, ethUsdPrice }) {
  const gas = BigInt(gasLimit);
  const fee = BigInt(maxFeePerGas);
  const price = BigInt(ethUsdPrice);
  if (gas <= 0n || fee < 0n || price <= 0n) throw new TypeError("invalid Ethereum gas fee or ETH/USD price");
  const numerator = gas * fee * price * USDT_SCALE;
  const denominator = ETH_SCALE * USD_SCALE;
  return (numerator + denominator - 1n) / denominator;
}

export function isReturnRefundEligible(quote) {
  return (quote?.status === "returned" || quote?.status === "refund_waiting_funds") &&
    quote.refundTxHash === undefined && quote.refundNonce === undefined;
}

export async function executeReturnRefund({
  ledger, quote, ledgerSha, saveLedger, ethereum, usdt, signer,
  refundRecipient, amount, sobyaConfirmations = 2, ethereumConfirmations = 12,
  applyConfirmedPriceChange, getEthUsdPrice
}) {
  if (!isReturnRefundEligible(quote)) return { ledger, ledgerSha, completed: false, skipped: true };
  if (!ledger.returnQuotes?.some(item => item.orderId === quote.orderId && item === quote)) {
    throw new Error("Return quote must belong to the supplied ledger");
  }
  if ((quote.status !== "returned" && quote.status !== "refund_waiting_funds") ||
      !/^0x[0-9a-fA-F]{40}$/.test(refundRecipient) ||
      refundRecipient.toLowerCase() !== quote.sender.toLowerCase() ||
      amount <= 0n || amount.toString() !== String(quote.payoutAmountAtomic)) {
    throw new Error("USDT refund recipient or gross amount does not match the confirmed return quote");
  }
  if (!quote.returnTxHash || !Number.isSafeInteger(quote.returnBlockNumber) ||
      typeof saveLedger !== "function" || typeof applyConfirmedPriceChange !== "function" ||
      typeof getEthUsdPrice !== "function") {
    throw new Error("confirmed SOBYA return, durable adapters, and ETH/USD fee pricing are required");
  }
  const returnReceipt = await ethereum.sobyaProvider.getTransactionReceipt(quote.returnTxHash);
  if (!returnReceipt || returnReceipt.status !== 1) throw new Error("SOBYA return transaction is not confirmed successfully");
  const returnHead = await ethereum.sobyaProvider.getBlockNumber();
  if (returnHead - returnReceipt.blockNumber + 1 < sobyaConfirmations) throw new Error("SOBYA return confirmation threshold not reached");

  calculateNextPrice({
    currentPrice: ledger.currentPriceUsdtPerSoby ?? AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby,
    quantitySobyAtomic: quote.paymentAmountAtomic,
    direction: "down"
  });

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

  const ethUsdPrice = BigInt(await getEthUsdPrice());
  const networkFeeUsdtAtomic = calculateUsdtNetworkFeeAtomic({
    gasLimit: gasLimit.toString(), maxFeePerGas: maxFeePerGas.toString(), ethUsdPrice
  });
  const netRefundAmount = amount - networkFeeUsdtAtomic;
  if (netRefundAmount <= 0n) throw new Error("Ethereum network fee exceeds the quoted USDT refund; manual review required");
  const balance = await usdt.balanceOf(signer.address);
  if (balance < netRefundAmount) {
    quote.status = "refund_waiting_funds";
    quote.refundWaitReason = "Insufficient USDT inventory for net refund after estimated Ethereum network fee";
    quote.requiredUsdtAtomic = netRefundAmount.toString();
    ledgerSha = await saveLedger(ledger, ledgerSha, "Hold USDT refund until inventory is funded " + quote.orderId);
    return { ledger, ledgerSha, completed: false, waitingForFunds: true };
  }

  const requiredEth = calculateRequiredPayoutBalance({
    payoutAmountAtomic: "1", gasLimit: gasLimit.toString(), maxFeePerGas: maxFeePerGas.toString()
  }) - 1n;
  const ethBalance = await ethereum.getBalance(signer.address);
  if (ethBalance < requiredEth) {
    quote.status = "refund_waiting_funds";
    quote.refundWaitReason = "Insufficient ETH gas reserve; the user network fee is deducted from the USDT refund";
    quote.requiredEthGasAtomic = requiredEth.toString();
    quote.estimatedNetworkFeeUsdtAtomic = networkFeeUsdtAtomic.toString();
    ledgerSha = await saveLedger(ledger, ledgerSha, "Hold USDT refund until ETH gas reserve is funded " + quote.orderId);
    return { ledger, ledgerSha, completed: false, waitingForFunds: true };
  }

  const nonce = await ethereum.getTransactionCount(signer.address, "pending");
  quote.refundNonce = nonce;
  quote.status = "refund_prepared";
  quote.refundPreparedAt = new Date().toISOString();
  quote.estimatedNetworkFeeUsdtAtomic = networkFeeUsdtAtomic.toString();
  quote.netRefundAmountAtomic = netRefundAmount.toString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Reserve Ethereum nonce for USDT refund " + quote.orderId);

  const tx = await usdt.transfer(refundRecipient, netRefundAmount, { nonce, gasLimit, ...feeOverrides });
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
        BigInt(parsed.args.value) === netRefundAmount;
    } catch { return false; }
  });
  if (!transferConfirmed) {
    quote.status = "review";
    quote.refundReviewReason = "Successful Ethereum receipt did not contain the exact net USDT Transfer event";
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
  settled.actualRefundAmountAtomic = netRefundAmount.toString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Confirm net USDT refund and reduce SOBYA price for " + quote.orderId);
  return { ledger, ledgerSha, completed: true, review: false };
}
