// Public browser settings only. Never put private keys or API secrets here.
window.SOBYA_BUY_CONFIG = Object.freeze({
  paymentsEnabled: false,
  apiBaseUrl: "https://sobya-chain.snforem.workers.dev",
  sobyaChainId: 357812033857,
  sobyaRpcUrl: "https://sobya-evm-rpc.nodesafe-app.xyz",
  sobyaExplorerUrl: "https://explorer.nodesafe-app.xyz/sobya",
  projectReceivingAddress: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
  // Owner-confirmed customer payment destinations; distinct from the SOBY inventory wallet.
  paymentReceivingAddresses: Object.freeze({
    ETH_ETHEREUM: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
    USDT_ETHEREUM: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
    BNB_BSC: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
    SOL_SOLANA: "ACTkwKD9ZhHYgRSEoM7QWvp5ig1cUxDo3gMzB55rocdk"
  }),
  inventoryWalletAddress: "0xebdb899fFE84a89e1d576964b640491c135651AD",
  // Approved opening reference price; not an active quote until the backend is deployed.
  salePriceUsd: 0.005,
  pricing: {
    referencePriceUsd: 0.005,
    quoteTtlSeconds: 600,
    mode: "asymmetric_demand_inventory",
    automaticQuotesEnabled: false
  },
  minimumConfirmations: { ethereum: 12, bsc: 15, solana: "finalized" },
  assets: {
    USDT_ETH: { symbol: "USDT", network: "Ethereum", chainId: 1, decimals: 6, contract: "0xdAC17F958D2ee523a2206206994597C13D831ec7", kind: "erc20" },
    ETH: { symbol: "ETH", network: "Ethereum", chainId: 1, decimals: 18, kind: "native" },
    BNB: { symbol: "BNB", network: "BNB Smart Chain", chainId: 56, decimals: 18, kind: "native" },
    SOL_SOLANA: { symbol: "SOL", network: "Solana", networkId: "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp", decimals: 9, kind: "native" }
  }
});
