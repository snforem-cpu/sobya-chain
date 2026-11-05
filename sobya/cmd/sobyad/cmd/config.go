package cmd

import (
	cmtcfg "github.com/cometbft/cometbft/config"
	serverconfig "github.com/cosmos/cosmos-sdk/server/config"
	evmserverconfig "github.com/cosmos/evm/server/config"
)

// initCometBFTConfig helps to override default CometBFT Config values.
// return cmtcfg.DefaultConfig if no custom configuration is required for the application.
func initCometBFTConfig() *cmtcfg.Config {
	cfg := cmtcfg.DefaultConfig()

	// Keep CometBFT query/admin RPC private by default. Operators expose
	// read-only routes only through a separately hardened TLS reverse proxy.
	cfg.RPC.ListenAddress = "tcp://127.0.0.1:26657"
	cfg.RPC.Unsafe = false
	cfg.P2P.ListenAddress = "tcp://0.0.0.0:26656"

	// these values put a higher strain on node memory
	// cfg.P2P.MaxNumInboundPeers = 100
	// cfg.P2P.MaxNumOutboundPeers = 40

	return cfg
}

// initAppConfig helps to override default appConfig template and configs.
// return "", nil if no custom configuration is required for the application.
// defaultAppConfig returns the combined Cosmos SDK and Cosmos EVM app.toml
// configuration used by both normal node startup and generated testnets.
func defaultAppConfig() *evmserverconfig.Config {
	srvCfg := serverconfig.DefaultConfig()
	// Cosmos SDK defaults its application mempool to disabled (-1). Cosmos EVM
	// requires the unified EVM/Cosmos mempool for CheckTx and proposal handling.
	// Keep a bounded queue instead of silently starting with EVM disabled.
	srvCfg.Mempool.MaxTxs = 5000

	evmCfg := evmserverconfig.DefaultEVMConfig()
	// Development-only EVM chain ID. A production ID must be explicitly selected
	// before generating a public genesis.
	evmCfg.EVMChainID = 777777

	jsonRPC := evmserverconfig.DefaultJSONRPCConfig()
	// The upstream Cosmos EVM default permits insecure account unlocking.
	// SOBYA never enables that on an operator-facing node. Keep JSON-RPC bound
	// to loopback by default; a reviewed TLS reverse proxy may expose it later.
	jsonRPC.AllowInsecureUnlock = false
	jsonRPC.EnableProfiling = false
	jsonRPC.MaxOpenConnections = 100
	jsonRPC.WSOrigins = []string{"127.0.0.1", "localhost"}

	return &evmserverconfig.Config{
		Config:  *srvCfg,
		EVM:     *evmCfg,
		JSONRPC: *jsonRPC,
		TLS:     *evmserverconfig.DefaultTLSConfig(),
	}
}

func initAppConfig() (string, interface{}) {
	// Preserve Cosmos SDK settings while adding the complete EVM server
	// configuration, including JSON-RPC and WebSocket defaults.
	customAppTemplate := serverconfig.DefaultConfigTemplate + evmserverconfig.DefaultEVMConfigTemplate
	return customAppTemplate, defaultAppConfig()
}
