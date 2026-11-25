import { JsonRpcProvider, getAddress } from "ethers";
import { AUTO_EXCHANGE_POLICY } from "./config.js";
import { ETHEREUM_USDT } from "./quote-ledger.js";

const ethereumUrl = process.env.ETHEREUM_RPC_URL || "https://ethereum-rpc.publicnode.com";
const sobyaCandidates = [
  process.env.SOBYA_EVM_RPC_URL || "https://sobya-evm-rpc.nodesafe-app.xyz",
  process.env.SOBYA_EVM_RPC_FALLBACK_URL || "https://sobya-rpc.nodesafe-dapp.xyz"
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
      console.log("SOBYA EVM RPC: OK; endpoint=" + url + "; chainId=" + network.chainId +
        "; latestBlock=" + height + "; inventoryNativeBalanceAtomic=" + balance.toString());
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
