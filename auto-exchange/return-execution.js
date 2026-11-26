import { Transaction } from "ethers";
import { calculateRequiredPayoutBalance } from "./payout-policy.js";
import { calculateNextPrice } from "./pricing.js";
import { AUTO_EXCHANGE_POLICY } from "./config.js";

const ETH_SCALE = 10n ** 18n;
const USD_SCALE = 10n ** 8n;
const USDT_SCALE = 10n ** 6n;
const USDT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7";

export function calculateUsdtNetworkFeeAtomic({ gasLimit, maxFeePerGas, ethUsdPrice }) {
  const gas = BigInt(gasLimit);
  const fee = BigInt(maxFeePerGas);
  const price = BigInt(ethUsdPrice);
  if (gas <= 0n || fee < 0n || price <= 0n) throw new TypeError("invalid Ethereum gas fee or ETH/USD price");
  const numerator = gas * fee * price * USDT_SCALE;
  const denominator = ETH_SCALE * USD_SCALE;
  return (numerator + denominator - 1n) / denominator;
}

function hasRecoverablePreparedTransaction(quote) {
  const tx = quote?.refundTransaction;
  return quote?.status === "refund_prepared" &&
    typeof quote.refundTxHash === "string" && /^0x[0-9a-fA-F]{64}$/.test(quote.refundTxHash) &&
    Number.isSafeInteger(quote.refundNonce) && tx && tx.chainId === AUTO_EXCHANGE_POLICY.ethereumChainId &&
    tx.to?.toLowerCase() === USDT_ADDRESS.toLowerCase() &&
    typeof tx.data === "string" && /^0x[0-9a-fA-F]+$/.test(tx.data) &&
    tx.value === "0" && /^\d+$/.test(String(tx.gasLimit)) &&
    ((/^\d+$/.test(String(tx.gasPrice))) ||
      (/^\d+$/.test(String(tx.maxFeePerGas)) && /^\d+$/.test(String(tx.maxPriorityFeePerGas))));
}

export function isReturnRefundEligible(quote) {
  return ((quote?.status === "returned" || quote?.status === "refund_waiting_funds") &&
    quote.refundTxHash === undefined && quote.refundNonce === undefined) ||
    hasRecoverablePreparedTransaction(quote);
}

function transactionRequestFromQuote(quote) {
  const stored = quote.refundTransaction;
  const request = {
    chainId: stored.chainId,
    nonce: quote.refundNonce,
    to: stored.to,
    data: stored.data,
    value: BigInt(stored.value),
    gasLimit: BigInt(stored.gasLimit)
  };
  if (stored.gasPrice !== undefined) request.gasPrice = BigInt(stored.gasPrice);
  else {
    request.maxFeePerGas = BigInt(stored.maxFeePerGas);
    request.maxPriorityFeePerGas = BigInt(stored.maxPriorityFeePerGas);
  }
  return request;
}

async function confirmAndSettle({
  ledger, quote, ledgerSha, saveLedger, ethereum, usdt, signer, refundRecipient,
  netRefundAmount, maxFeePerGas, receipt, applyConfirmedPriceChange
}) {
  if (receipt?.status !== 1) {
    quote.status = "review";
    quote.refundReviewReason = "Ethereum USDT refund transaction did not confirm successfully";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag USDT refund transaction failure " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }
  const transferConfirmed = (receipt.logs || []).some(log => {
    if (String(log.address).toLowerCase() !== USDT_ADDRESS.toLowerCase()) return false;
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

export async function executeReturnRefund({
  ledger, quote, ledgerSha, saveLedger, ethereum, usdt, signer,
  refundRecipient, amount, sobyaConfirmations = 2, ethereumConfirmations = 12,
  applyConfirmedPriceChange, getEthUsdPrice
}) {
  if (!isReturnRefundEligible(quote)) return { ledger, ledgerSha, completed: false, skipped: true };
  if (!ledger.returnQuotes?.some(item => item.orderId === quote.orderId && item === quote)) {
    throw new Error("Return quote must belong to the supplied ledger");
  }
  const recovering = quote.status === "refund_prepared";
  if ((!recovering && quote.status !== "returned" && quote.status !== "refund_waiting_funds") ||
      !/^0x[0-9a-fA-F]{40}$/.test(refundRecipient) ||
      refundRecipient.toLowerCase() !== quote.sender.toLowerCase() ||
      amount <= 0n || amount.toString() !== String(quote.payoutAmountAtomic)) {
    throw new Error("USDT refund recipient or gross amount does not match the confirmed return quote");
  }
  if (!quote.returnTxHash || !Number.isSafeInteger(quote.returnBlockNumber) ||
      typeof saveLedger !== "function" || typeof applyConfirmedPriceChange !== "function") {
    throw new Error("confirmed SOBYA return, durable adapters, and price settlement adapter are required");
  }
  const returnReceipt = await ethereum.sobyaProvider.getTransactionReceipt(quote.returnTxHash);
  if (!returnReceipt || returnReceipt.status !== 1) throw new Error("SOBYA return transaction is not confirmed successfully");
  const returnHead = await ethereum.sobyaProvider.getBlockNumber();
  if (returnHead - returnReceipt.blockNumber + 1 < sobyaConfirmations) throw new Error("SOBYA return confirmation threshold not reached");

  let netRefundAmount;
  let maxFeePerGas;
  if (!recovering) {
    if (typeof getEthUsdPrice !== "function") throw new Error("ETH/USD fee pricing adapter is required");
    calculateNextPrice({
      currentPrice: ledger.currentPriceUsdtPerSoby ?? AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby,
      quantitySobyAtomic: quote.paymentAmountAtomic,
      direction: "down"
    });
    const estimatedGas = await usdt.transfer.estimateGas(refundRecipient, amount);
    const gasLimit = (estimatedGas * 12_000n + 9_999n) / 10_000n;
    const feeData = await ethereum.getFeeData();
    let feeOverrides;
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
    netRefundAmount = amount - networkFeeUsdtAtomic;
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
    const txRequest = {
      chainId: AUTO_EXCHANGE_POLICY.ethereumChainId,
      nonce, to: USDT_ADDRESS,
      data: usdt.interface.encodeFunctionData("transfer", [refundRecipient, netRefundAmount]),
      value: 0n, gasLimit, ...feeOverrides
    };
    const signedTransaction = await signer.signTransaction(txRequest);
    const signedHash = Transaction.from(signedTransaction).hash;
    if (!signedHash) throw new Error("Could not derive deterministic Ethereum refund transaction hash");
    quote.refundNonce = nonce;
    quote.refundTxHash = signedHash;
    quote.refundTransaction = {
      chainId: AUTO_EXCHANGE_POLICY.ethereumChainId,
      to: USDT_ADDRESS,
      data: txRequest.data,
      value: "0",
      gasLimit: gasLimit.toString(),
      ...(feeOverrides.gasPrice != null
        ? { gasPrice: feeOverrides.gasPrice.toString() }
        : { maxFeePerGas: feeOverrides.maxFeePerGas.toString(),
            maxPriorityFeePerGas: feeOverrides.maxPriorityFeePerGas.toString() })
    };
    quote.status = "refund_prepared";
    quote.refundPreparedAt = new Date().toISOString();
    quote.estimatedNetworkFeeUsdtAtomic = networkFeeUsdtAtomic.toString();
    quote.netRefundAmountAtomic = netRefundAmount.toString();
    ledgerSha = await saveLedger(ledger, ledgerSha, "Persist signed USDT refund intent before broadcast " + quote.orderId);
  }

  if (!hasRecoverablePreparedTransaction(quote)) {
    quote.status = "review";
    quote.refundReviewReason = "Prepared refund lacks a verifiable deterministic transaction intent; manual reconciliation required";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag incomplete prepared USDT refund for manual review " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }
  const txRequest = transactionRequestFromQuote(quote);
  const signedTransaction = await signer.signTransaction(txRequest);
  const signedHash = Transaction.from(signedTransaction).hash;
  if (!signedHash || signedHash.toLowerCase() !== quote.refundTxHash.toLowerCase()) {
    quote.status = "review";
    quote.refundReviewReason = "Reconstructed signed refund does not match the persisted transaction hash";
    ledgerSha = await saveLedger(ledger, ledgerSha, "Flag mismatched prepared USDT refund " + quote.orderId);
    return { ledger, ledgerSha, completed: false, review: true };
  }
  netRefundAmount = BigInt(quote.netRefundAmountAtomic);
  maxFeePerGas = txRequest.maxFeePerGas ?? txRequest.gasPrice;

  let receipt = await ethereum.getTransactionReceipt(quote.refundTxHash);
  if (!receipt) {
    const pending = await ethereum.getTransaction(quote.refundTxHash);
    if (!pending) {
      try {
        await ethereum.broadcastTransaction(signedTransaction);
      } catch (error) {
        // "already known" and ambiguous transport errors are reconciled by the
        // deterministic hash below; never create a replacement transaction.
        const afterErrorReceipt = await ethereum.getTransactionReceipt(quote.refundTxHash);
        const afterErrorTx = afterErrorReceipt ? null : await ethereum.getTransaction(quote.refundTxHash);
        if (!afterErrorReceipt && !afterErrorTx) throw error;
        receipt = afterErrorReceipt;
      }
    }
  }
  if (!receipt) {
    receipt = await ethereum.waitForTransaction(quote.refundTxHash, ethereumConfirmations);
  }
  if (!receipt) {
    return { ledger, ledgerSha, completed: false, pending: true };
  }
  const currentEthHead = await ethereum.getBlockNumber();
  if (currentEthHead - receipt.blockNumber + 1 < ethereumConfirmations) {
    const confirmed = await ethereum.waitForTransaction(quote.refundTxHash, ethereumConfirmations);
    if (!confirmed) return { ledger, ledgerSha, completed: false, pending: true };
    receipt = confirmed;
  }
  quote.status = "refund_broadcast";
  quote.refundBroadcastAt = quote.refundBroadcastAt ?? new Date().toISOString();
  ledgerSha = await saveLedger(ledger, ledgerSha, "Reconcile deterministic USDT refund broadcast " + quote.orderId);
  return confirmAndSettle({
    ledger, quote, ledgerSha, saveLedger, ethereum, usdt, signer, refundRecipient,
    netRefundAmount, maxFeePerGas, receipt, applyConfirmedPriceChange
  });
}
