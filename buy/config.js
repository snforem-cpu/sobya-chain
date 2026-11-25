// Public browser settings only. Never put private keys or API secrets here.
window.SOBYA_BUY_CONFIG = Object.freeze({
  paymentsEnabled: false,
  apiBaseUrl: "https://sobya-chain.snforem.workers.dev",
  sobyaChainId: 357812033857,
  sobyaRpcUrl: "https://sobya-evm-rpc.nodesafe-dapp.xyz",
  sobyaExplorerUrl: "https://explorer.nodesafe-app.xyz/sobya",
  projectReceivingAddress: "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f",
  // Owner-maintained reference price for the manual request desk.
  salePriceUsd: 0.005
});
