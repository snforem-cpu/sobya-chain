import {
  Contract, JsonRpcProvider, Wallet, getAddress, parseUnits, ZeroAddress
} from "ethers";

const SOURCE_CHAIN_ID = 1n;
const DESTINATION_CHAIN_ID = 357812033857n;
const USDT_ETHEREUM = "0xdAC17F958D2ee523a2206206994597C13D831ec7";
const ESCROW_ABI = [
  "function paymentToken() view returns(address)",
  "function operator() view returns(address)",
  "function treasury() view returns(address)",
  "function orders(bytes32) view returns(address depositor,address recipient,uint128 paymentAmount,uint128 sobyAmount,uint64 deadline,bool fulfilled,bool refunded,bool paymentReleased)",
  "function markFulfilled(bytes32)",
  "function releasePayment(bytes32)",
  "event OrderDeposited(bytes32 indexed orderId,address indexed depositor,address indexed recipient,uint256 paymentAmount,uint256 sobyAmount,uint64 deadline)"
];
const VAULT_ABI = [
  "function relayer() view returns(address)",
  "function processedOrders(bytes32) view returns(bool)",
  "function release(bytes32,address payable,uint256)"
];

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required configuration: ${name}`);
  return value;
}

export function expectedSoby(paymentAmount, sobyPerUsdt) {
  const rateWei = parseUnits(sobyPerUsdt, 18);
  const amount = BigInt(paymentAmount);
  const divisor = 1_000_000n;
  if (amount <= 0n || rateWei <= 0n) throw new Error("Amounts and conversion rate must be positive");
  if ((amount * rateWei) % divisor !== 0n) throw new Error("Quote cannot be represented exactly in SOBY wei");
  return (amount * rateWei) / divisor;
}

async function githubRequest(path, token, options = {}) {
  const response = await fetch(`https://api.github.com/repos/${required("GITHUB_REPOSITORY")}/${path}`, {
    ...options,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(options.headers || {})
    }
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`GitHub state API ${response.status}: ${body.slice(0, 500)}`);
  return body ? JSON.parse(body) : null;
}

async function readCheckpoint(token, stateBranch, deploymentBlock) {
  const path = `contents/ops/crosschain-state.json?ref=${encodeURIComponent(stateBranch)}`;
  const file = await githubRequest(path, token);
  const state = JSON.parse(Buffer.from(file.content, "base64").toString("utf8"));
  if (state.schema !== 1) throw new Error("Unsupported checkpoint schema");
  return { path: "ops/crosschain-state.json", sha: file.sha, nextBlock: state.nextEthereumBlock ?? deploymentBlock };
}

async function saveCheckpoint(token, stateBranch, checkpoint, nextBlock) {
  const content = Buffer.from(JSON.stringify({
    schema: 1,
    nextEthereumBlock: nextBlock,
    updatedAt: new Date().toISOString()
  }, null, 2) + "\n").toString("base64");
  await githubRequest(checkpoint.path, token, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: `Advance SOBYA cross-chain scan checkpoint to block ${nextBlock}`,
      content,
      sha: checkpoint.sha,
      branch: stateBranch
    })
  });
}

async function waitFinal(tx, confirmations, label) {
  const receipt = await tx.wait(confirmations);
  if (!receipt || receipt.status !== 1) throw new Error(`${label} transaction failed`);
  return receipt;
}

export async function main() {
  const ethereumRpc = required("ETHEREUM_RPC_URL");
  const sobyaRpc = required("SOBYA_EVM_RPC_URL");
  const escrowAddress = getAddress(required("ETHEREUM_ESCROW_ADDRESS"));
  const vaultAddress = getAddress(required("SOBYA_PAYOUT_VAULT_ADDRESS"));
  const treasuryAddress = getAddress(required("SOBYA_TREASURY_ADDRESS"));
  const deploymentBlock = Number(required("ETHEREUM_DEPLOYMENT_BLOCK"));
  const span = Number(process.env.SCAN_BLOCK_SPAN || "1500");
  const sourceConfirmations = Number(process.env.ETHEREUM_CONFIRMATIONS || "12");
  const destinationConfirmations = Number(process.env.SOBYA_CONFIRMATIONS || "2");
  const maxUsdt = BigInt(required("MAX_USDT_MICRO"));
  const maxSoby = BigInt(required("MAX_SOBY_WEI"));
  const sobyPerUsdt = required("SOBY_PER_USDT");
  const minDeadlineSeconds = Number(process.env.MIN_DEADLINE_REMAINING_SECONDS || "7200");
  if (!Number.isSafeInteger(deploymentBlock) || deploymentBlock < 0 ||
      !Number.isSafeInteger(span) || span < 1 || span > 5000 ||
      sourceConfirmations < 1 || destinationConfirmations < 1 ||
      maxUsdt <= 0n || maxSoby <= 0n || minDeadlineSeconds < 600) {
    throw new Error("Invalid scanner limits or confirmation configuration");
  }

  const sourceProvider = new JsonRpcProvider(ethereumRpc, 1, { staticNetwork: true });
  const destinationProvider = new JsonRpcProvider(sobyaRpc, Number(DESTINATION_CHAIN_ID), { staticNetwork: true });
  const [sourceNetwork, destinationNetwork] = await Promise.all([
    sourceProvider.getNetwork(), destinationProvider.getNetwork()
  ]);
  if (sourceNetwork.chainId !== SOURCE_CHAIN_ID) throw new Error("Ethereum RPC chain ID mismatch");
  if (destinationNetwork.chainId !== DESTINATION_CHAIN_ID) throw new Error("SOBYA EVM RPC chain ID mismatch");

  const operator = new Wallet(required("ETHEREUM_OPERATOR_PRIVATE_KEY"), sourceProvider);
  const relayer = new Wallet(required("SOBYA_RELAYER_PRIVATE_KEY"), destinationProvider);
  const escrow = new Contract(escrowAddress, ESCROW_ABI, operator);
  const vault = new Contract(vaultAddress, VAULT_ABI, relayer);

  const [tokenAddress, configuredOperator, configuredTreasury, configuredRelayer] = await Promise.all([
    escrow.paymentToken(), escrow.operator(), escrow.treasury(), vault.relayer()
  ]);
  if (getAddress(tokenAddress) !== getAddress(USDT_ETHEREUM)) throw new Error("Escrow is not configured for canonical Ethereum USDT");
  if (getAddress(configuredOperator) !== getAddress(operator.address)) throw new Error("Ethereum operator key does not match escrow operator");
  if (getAddress(configuredTreasury) !== treasuryAddress) throw new Error("Configured treasury does not match escrow treasury");
  if (getAddress(configuredRelayer) !== getAddress(relayer.address)) throw new Error("SOBYA relayer key does not match payout vault relayer");

  const head = await sourceProvider.getBlockNumber();
  const finalizedHead = head - sourceConfirmations;
  const stateBranch = process.env.CROSSCHAIN_STATE_BRANCH || "sobya-crosschain-state";
  const token = required("GITHUB_TOKEN");
  const checkpoint = await readCheckpoint(token, stateBranch, deploymentBlock);
  const fromBlock = checkpoint.nextBlock;
  if (fromBlock > finalizedHead) {
    console.log(JSON.stringify({ status: "idle", fromBlock, finalizedHead }));
    return;
  }
  const toBlock = Math.min(finalizedHead, fromBlock + span - 1);
  const filter = escrow.filters.OrderDeposited();
  const events = await escrow.queryFilter(filter, fromBlock, toBlock);
  let paid = 0;
  let expired = 0;

  for (const event of events) {
    const { orderId, depositor, recipient, paymentAmount, sobyAmount, deadline } = event.args;
    const order = await escrow.orders(orderId);
    if (getAddress(order.depositor) === ZeroAddress || order.refunded) continue;
    if (getAddress(order.depositor) !== getAddress(depositor) ||
        getAddress(order.recipient) !== getAddress(recipient) ||
        order.paymentAmount !== paymentAmount || order.sobyAmount !== sobyAmount ||
        order.deadline !== deadline) {
      throw new Error(`Escrow event/order mismatch for ${orderId}`);
    }
    const payment = BigInt(paymentAmount);
    const payout = BigInt(sobyAmount);
    if (payment > maxUsdt || payout > maxSoby || payout !== expectedSoby(payment, sobyPerUsdt)) {
      throw new Error(`Order ${orderId} violates the published quote or configured limits; manual review required`);
    }
    if (getAddress(recipient) === ZeroAddress) throw new Error(`Order ${orderId} has a zero recipient`);

    const latestSourceBlock = await sourceProvider.getBlock("latest");
    if (!latestSourceBlock || Number(deadline) <= latestSourceBlock.timestamp + minDeadlineSeconds) {
      expired++;
      console.log(`Skipping expired/near-expiry order ${orderId}; buyer refund remains available`);
      continue;
    }

    if (!(await vault.processedOrders(orderId))) {
      const payoutTx = await vault.release(orderId, recipient, payout);
      await waitFinal(payoutTx, destinationConfirmations, "SOBYA inventory payout");
      if (!(await vault.processedOrders(orderId))) throw new Error(`Vault did not record payout for ${orderId}`);
    }

    const refreshed = await escrow.orders(orderId);
    if (refreshed.refunded) throw new Error(`Order ${orderId} was refunded after SOBYA payout; stop for manual reconciliation`);
    if (!refreshed.fulfilled) {
      const fulfillTx = await escrow.markFulfilled(orderId);
      await waitFinal(fulfillTx, sourceConfirmations, "Ethereum fulfillment");
    }
    const afterFulfillment = await escrow.orders(orderId);
    if (!afterFulfillment.fulfilled || afterFulfillment.refunded) {
      throw new Error(`Escrow fulfillment state is inconsistent for ${orderId}`);
    }
    if (!afterFulfillment.paymentReleased) {
      const releaseTx = await escrow.releasePayment(orderId);
      await waitFinal(releaseTx, sourceConfirmations, "Ethereum USDT treasury release");
    }
    const finalOrder = await escrow.orders(orderId);
    if (!finalOrder.paymentReleased) throw new Error(`USDT treasury release not recorded for ${orderId}`);
    paid++;
    console.log(`Settled ${orderId}: ${payment} USDT base units -> ${payout} SOBY wei`);
  }

  await saveCheckpoint(token, stateBranch, checkpoint, toBlock + 1);
  console.log(JSON.stringify({ status: "scanned", fromBlock, toBlock, events: events.length, settled: paid, skippedExpired: expired }));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error("[sobya-crosschain-worker]", error);
    process.exitCode = 1;
  });
}
