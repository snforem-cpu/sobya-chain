// Public browser settings only. Never put private keys or API secrets here.
window.SOBYA_BUY_CONFIG = Object.freeze({
  paymentsEnabled: false,
  apiBaseUrl: "",
  sobyaChainId: 357812033857,
  sobyaRpcUrl: "https://sobya-evm-rpc.nodesafe-app.xyz",
  sobyaExplorerUrl: "https://explorer.nodesafe-app.xyz/sobya",
  projectReceivingAddress: "",
  salePriceUsd: null,
  minimumConfirmations: { ethereum: 12, bsc: 15 },
  assets: {
    USDT_ETH: { symbol: "USDT", network: "Ethereum", chainId: 1, decimals: 6, contract: "0xdAC17F958D2ee523a2206206994597C13D831ec7", kind: "erc20" },
    ETH: { symbol: "ETH", network: "Ethereum", chainId: 1, decimals: 18, kind: "native" },
    BNB: { symbol: "BNB", network: "BNB Smart Chain", chainId: 56, decimals: 18, kind: "native" }
  }
});
