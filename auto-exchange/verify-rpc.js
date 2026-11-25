import { JsonRpcProvider, getAddress } from "ethers";
import { AUTO_EXCHANGE_POLICY } from "./config.js";
import { ETHEREUM_USDT } from "./quote-ledger.js";

const endpoints = {
  ethereum: process.env.ETHEREUM_RPC_URL || "https://ethereum-rpc.publicnode.com",
  sobya: process.env.SOBYA_EVM_RPC_URL || "https://sobya-evm-rpc.nodesafe-app.xyz"
};
const inventory = getAddress(AUTO_EXCHANGE_POLICY.inventoryWalletEvmAddress);
const checks = [
  { name: "Ethereum", url: endpoints.ethereum, expectedChainId: AUTO_EXCHANGE_POLICY.ethereumChainId },
  { name: "SOBYA", url: endpoints.sobya, expectedChainId: AUTO_EXCHANGE_POLICY.sobyaEvmChainId }
];
let failed = false;

for (const item of checks) {
  const provider = new JsonRpcProvider(item.url, undefined, { staticNetwork: false });
  try {
    const network = await provider.getNetwork();
    const height = await provider.getBlockNumber();
    if (Number(network.chainId) !== item.expectedChainId) {
      throw new Error("wrong chain ID: expected " + item.expectedChainId + ", received " + network.chainId);
    }
    if (!Number.isSafeInteger(height) || height <= 0) throw new Error("invalid latest block height");
    console.log(item.name + " RPC: OK; chainId=" + network.chainId + "; latestBlock=" + height);
    if (item.name === "Ethereum") {
      const code = await provider.getCode(ETHEREUM_USDT);
      if (code === "0x") throw new Error("Ethereum USDT contract has no bytecode at configured address");
      console.log("Ethereum USDT contract: OK; bytecodeLength=" + (code.length - 2));
    } else {
      const balance = await provider.getBalance(inventory);
      console.log("SOBYA inventory address: OK; nativeBalanceAtomic=" + balance.toString());
    }
  } catch (error) {
    failed = true;
    console.error(item.name + " RPC: FAILED; " + String(error.message || error));
  } finally {
    await provider.destroy();
  }
}
if (failed) process.exitCode = 1;
