import { JsonRpcProvider, Contract, getAddress } from "ethers";
import { AUTO_EXCHANGE_POLICY } from "./config.js";
import { ETHEREUM_USDT } from "./quote-ledger.js";

const ethereumUrl = process.env.ETHEREUM_RPC_URL || "https://ethereum-rpc.publicnode.com";
const sobyaCandidates = [
  process.env.SOBYA_EVM_RPC_URL || "https://sobya-evm-rpc.nodesafe-dapp.xyz",
  process.env.SOBYA_EVM_RPC_FALLBACK_URL || "https://sobya-evm-rpc.nodesafe-app.xyz"
].filter((url, index, list) => url && list.indexOf(url) === index);
const inventory = getAddress(AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress);
let failed = false;

async function verifyEthereum() {
  const provider = new JsonRpcProvider(ethereumUrl, undefined, { staticNetwork: false });
  try {
    const network = await provider.getNetwork();
    const height = await provider.getBlockNumber();
    if (Number(network.chainId) !== AUTO_EXCHANGE_POLICY.ethereumChainId) {
      throw new Error("wrong chain ID: expected " + AUTO_EXCHANGE_POLICY.ethereumChainId + ", received " + network.chainId);
    }
    if (!Number.isSafeInteger(height) || height <= 0) throw new Error("invalid latest block height");
    console.log("Ethereum RPC: OK; chainId=" + network.chainId + "; latestBlock=" + height);
    const code = await provider.getCode(ETHEREUM_USDT);
    if (code === "0x") throw new Error("Ethereum USDT contract has no bytecode at configured address");
    console.log("Ethereum USDT contract: OK; bytecodeLength=" + (code.length - 2));
    const usdt = new Contract(ETHEREUM_USDT, ["function balanceOf(address) view returns (uint256)"], provider);
    const tokenBalance = await usdt.balanceOf(inventory);
    const nativeBalance = await provider.getBalance(inventory);
    console.log("Ethereum inventory balances: USDT atomic=" + tokenBalance.toString() + "; ETH wei=" + nativeBalance.toString());
    const ethFees = await provider.getFeeData();
    console.log("Ethereum fee RPC: " + (ethFees.maxFeePerGas != null || ethFees.gasPrice != null ? "OK" : "UNAVAILABLE") +
      "; gasPriceWei=" + (ethFees.gasPrice?.toString() ?? "null") +
      "; maxFeePerGasWei=" + (ethFees.maxFeePerGas?.toString() ?? "null") +
      "; maxPriorityFeePerGasWei=" + (ethFees.maxPriorityFeePerGas?.toString() ?? "null"));
  } catch (error) {
    failed = true;
    console.error("Ethereum RPC: FAILED; " + String(error.message || error));
  } finally {
    await provider.destroy();
  }
}

async function verifySobya() {
  const errors = [];
  for (const url of sobyaCandidates) {
    const provider = new JsonRpcProvider(url, undefined, { staticNetwork: false });
    try {
      const network = await provider.getNetwork();
      const height = await provider.getBlockNumber();
      if (Number(network.chainId) !== AUTO_EXCHANGE_POLICY.sobyaEvmChainId) {
        throw new Error("not the SOBYA EVM chain: expected " + AUTO_EXCHANGE_POLICY.sobyaEvmChainId + ", received " + network.chainId);
      }
      if (!Number.isSafeInteger(height) || height <= 0) throw new Error("invalid latest block height");
      const balance = await provider.getBalance(inventory);
      const fees = await provider.getFeeData();
      if (fees.maxFeePerGas == null && fees.gasPrice == null) throw new Error("RPC did not return usable EVM fee data");
      // eth_estimateGas simulates a transfer; it does not sign or broadcast a transaction.
      const estimatedGas = await provider.estimateGas({ from: inventory, to: inventory, value: 1n });
      if (estimatedGas <= 0n) throw new Error("eth_estimateGas returned a non-positive estimate");
      const maxFee = fees.maxFeePerGas ?? fees.gasPrice;
      const requiredGasReserve = estimatedGas * maxFee;
      console.log("SOBYA EVM RPC: OK; endpoint=" + url + "; chainId=" + network.chainId +
        "; latestBlock=" + height + "; inventoryNativeBalanceAtomic=" + balance.toString());
      console.log("SOBYA write-path simulation: OK; eth_estimateGas=" + estimatedGas.toString() +
        "; gasPriceWei=" + (fees.gasPrice?.toString() ?? "null") +
        "; maxFeePerGasWei=" + (fees.maxFeePerGas?.toString() ?? "null") +
        "; maxPriorityFeePerGasWei=" + (fees.maxPriorityFeePerGas?.toString() ?? "null") +
        "; estimatedGasReserveAtomic=" + requiredGasReserve.toString() +
        "; inventoryCoversSimulation=" + String(balance >= requiredGasReserve));
      return;
    } catch (error) {
      errors.push(url + " => " + String(error.message || error));
    } finally {
      await provider.destroy();
    }
  }
  failed = true;
  console.error("SOBYA EVM RPC: FAILED; " + errors.join(" | "));
}

await verifyEthereum();
await verifySobya();
if (failed) process.exitCode = 1;
