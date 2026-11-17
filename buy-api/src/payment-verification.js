const EVM_NETWORKS = Object.freeze({
  ETH_ETHEREUM: {
    chainId: 1,
    rpc: "https://ethereum-rpc.publicnode.com",
    recipient: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
    confirmations: 12,
    kind: "native",
    decimals: 18,
  },
  USDT_ETHEREUM: {
    chainId: 1,
    rpc: "https://ethereum-rpc.publicnode.com",
    recipient: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
    confirmations: 12,
    kind: "erc20",
    token: "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    decimals: 6,
  },
  BNB_BSC: {
    chainId: 56,
    rpc: "https://bsc-rpc.publicnode.com",
    recipient: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
    confirmations: 15,
    kind: "native",
    decimals: 18,
  },
});

const SOLANA_RPC = "https://api.mainnet-beta.solana.com";
const SOLANA_RECIPIENT = "ACTkwKD9ZhHYgRSEoM7QWvp5ig1cUxDo3gMzB55rocdk";
const TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";

function normalizeHexAddress(value) {
  return typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value)
    ? value.toLowerCase()
    : null;
}

async function rpcCall(url, method, params, fetchImpl = fetch) {
  const response = await fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (!response.ok) throw new Error("rpc_unavailable");
  const payload = await response.json();
  if (payload.error || payload.result === undefined) throw new Error("rpc_unavailable");
  return payload.result;
}

/**
 * Verifies a single EVM payment against a quote already stored by the server.
 * expectedAmount is the exact integer amount in the payment asset's base units.
 * The caller must enforce unique transaction hashes in D1 before accepting it.
 */
export async function verifyEvmPayment({
  asset, txHash, expectedAmount, expectedSender, fetchImpl = fetch,
}) {
  const network = EVM_NETWORKS[asset];
  if (!network || typeof txHash !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(txHash)) {
    throw new Error("invalid_payment_reference");
  }
  if (!/^\d+$/.test(String(expectedAmount)) || BigInt(expectedAmount) <= 0n) {
    throw new Error("invalid_expected_amount");
  }
  const sender = normalizeHexAddress(expectedSender);
  if (!sender) throw new Error("invalid_expected_sender");

  const [receipt, tx, headHex] = await Promise.all([
    rpcCall(network.rpc, "eth_getTransactionReceipt", [txHash], fetchImpl),
    rpcCall(network.rpc, "eth_getTransactionByHash", [txHash], fetchImpl),
    rpcCall(network.rpc, "eth_blockNumber", [], fetchImpl),
  ]);
  if (!receipt || !tx || receipt.status !== "0x1" || !receipt.blockNumber) {
    throw new Error("payment_not_successful");
  }
  if (Number(BigInt(tx.chainId || "0x0")) !== network.chainId) {
    throw new Error("wrong_payment_chain");
  }
  if (normalizeHexAddress(tx.from) !== sender) throw new Error("payment_sender_mismatch");

  const confirmations = Number(BigInt(headHex) - BigInt(receipt.blockNumber) + 1n);
  if (!Number.isSafeInteger(confirmations) || confirmations < network.confirmations) {
    throw new Error("payment_not_final");
  }

  let actualAmount;
  if (network.kind === "native") {
    if (normalizeHexAddress(tx.to) !== normalizeHexAddress(network.recipient)) throw new Error("wrong_payment_recipient");
    actualAmount = BigInt(tx.value || "0x0");
  } else {
    if (normalizeHexAddress(tx.to) !== normalizeHexAddress(network.token)) throw new Error("wrong_payment_asset");
    const matching = (receipt.logs || []).filter(log =>
      normalizeHexAddress(log.address) === normalizeHexAddress(network.token) &&
      log.topics?.[0]?.toLowerCase() === TRANSFER_TOPIC &&
      log.topics?.[1]?.slice(-40).toLowerCase() === sender.slice(2) &&
      log.topics?.[2]?.slice(-40).toLowerCase() === normalizeHexAddress(network.recipient).slice(2)
    );
    if (matching.length !== 1) throw new Error("payment_transfer_not_found");
    actualAmount = BigInt(matching[0].data || "0x0");
  }
  if (actualAmount !== BigInt(expectedAmount)) throw new Error("payment_amount_mismatch");

  return {
    verified: true,
    chainId: network.chainId,
    txHash,
    sender,
    recipient: network.recipient,
    amountBaseUnits: actualAmount.toString(),
    confirmations,
    blockNumber: Number(BigInt(receipt.blockNumber)),
  };
}

/**
 * Verifies a finalized native SOL transfer. The expected sender is the
 * connected Solana payer stored with the quote; no browser "paid" flag is used.
 */
export async function verifySolPayment({
  signature, expectedAmount, expectedSender, fetchImpl = fetch,
}) {
  if (typeof signature !== "string" || signature.length < 80 || signature.length > 100) {
    throw new Error("invalid_payment_reference");
  }
  if (!/^\d+$/.test(String(expectedAmount)) || BigInt(expectedAmount) <= 0n) {
    throw new Error("invalid_expected_amount");
  }
  if (typeof expectedSender !== "string" || expectedSender.length < 32 || expectedSender.length > 44) {
    throw new Error("invalid_expected_sender");
  }
  const result = await rpcCall(SOLANA_RPC, "getTransaction", [
    signature,
    { commitment: "finalized", encoding: "jsonParsed", maxSupportedTransactionVersion: 0 },
  ], fetchImpl);
  if (!result || result.meta?.err || result.meta?.confirmationStatus && result.meta.confirmationStatus !== "finalized") {
    throw new Error("payment_not_final");
  }
  const instructions = result.transaction?.message?.instructions || [];
  const transfers = instructions.filter(ix =>
    ix.program === "system" && ix.parsed?.type === "transfer" &&
    ix.parsed?.info?.source === expectedSender &&
    ix.parsed?.info?.destination === SOLANA_RECIPIENT
  );
  if (transfers.length !== 1) throw new Error("payment_transfer_not_found");
  const lamports = BigInt(transfers[0].parsed.info.lamports);
  if (lamports !== BigInt(expectedAmount)) throw new Error("payment_amount_mismatch");
  return {
    verified: true,
    chain: "solana-mainnet",
    signature,
    sender: expectedSender,
    recipient: SOLANA_RECIPIENT,
    amountBaseUnits: lamports.toString(),
    slot: result.slot,
    commitment: "finalized",
  };
}

export const paymentNetworkConfig = Object.freeze({
  ...Object.fromEntries(Object.entries(EVM_NETWORKS).map(([key, value]) => [key, {
    chainId: value.chainId, confirmations: value.confirmations,
    decimals: value.decimals, kind: value.kind,
  }])),
  SOL_SOLANA: { chain: "solana-mainnet", decimals: 9, commitment: "finalized" },
});


// SOBY is the native asset on SOBYA Mainnet (chain ID 357812033857),
// not an ERC-20 contract. The owner signs this transfer in MetaMask.
const SOBYA_RPC = "https://sobya-evm-rpc.nodesafe-app.xyz";
const SOBYA_CHAIN_ID = 357812033857;
const SOBYA_INVENTORY_WALLET = "0xebdb899fFE84a89e1d576964b640491c135651AD";

export async function verifyNativeSobyPayout({
  txHash, expectedAmount, expectedBuyer, fetchImpl = fetch,
}) {
  if (typeof txHash !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(txHash)) {
    throw new Error("invalid_payout_reference");
  }
  if (!/^\\d+$/.test(String(expectedAmount)) || BigInt(expectedAmount) <= 0n) {
    throw new Error("invalid_payout_amount");
  }
  const buyer = normalizeHexAddress(expectedBuyer);
  if (!buyer) throw new Error("invalid_payout_buyer");

  const [receipt, tx, headHex] = await Promise.all([
    rpcCall(SOBYA_RPC, "eth_getTransactionReceipt", [txHash], fetchImpl),
    rpcCall(SOBYA_RPC, "eth_getTransactionByHash", [txHash], fetchImpl),
    rpcCall(SOBYA_RPC, "eth_blockNumber", [], fetchImpl),
  ]);
  if (!receipt || !tx || receipt.status !== "0x1" || !receipt.blockNumber) {
    throw new Error("payout_not_successful");
  }
  if (Number(BigInt(tx.chainId || "0x0")) !== SOBYA_CHAIN_ID) {
    throw new Error("wrong_payout_chain");
  }
  if (normalizeHexAddress(tx.from) !== normalizeHexAddress(SOBYA_INVENTORY_WALLET)) {
    throw new Error("wrong_payout_sender");
  }
  if (normalizeHexAddress(tx.to) !== buyer) throw new Error("wrong_payout_recipient");
  if (BigInt(tx.value || "0x0") !== BigInt(expectedAmount)) {
    throw new Error("payout_amount_mismatch");
  }
  const confirmations = Number(BigInt(headHex) - BigInt(receipt.blockNumber) + 1n);
  if (!Number.isSafeInteger(confirmations) || confirmations < 12) {
    throw new Error("payout_not_final");
  }
  return {
    verified: true, chainId: SOBYA_CHAIN_ID, txHash,
    sender: SOBYA_INVENTORY_WALLET, recipient: buyer,
    amountBaseUnits: BigInt(tx.value).toString(), confirmations,
    blockNumber: Number(BigInt(receipt.blockNumber)),
  };
}
