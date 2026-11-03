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

	// these values put a higher strain on node memory
	// cfg.P2P.MaxNumInboundPeers = 100
	// cfg.P2P.MaxNumOutboundPeers = 40

	return cfg
}

// initAppConfig helps to override default appConfig template and configs.
// return "", nil if no custom configuration is required for the application.
func initAppConfig() (string, interface{}) {
	type CustomAppConfig struct {
		serverconfig.Config `mapstructure:",squash"`
		EVM     evmserverconfig.EVMConfig     `mapstructure:"evm"`
		JSONRPC evmserverconfig.JSONRPCConfig `mapstructure:"json-rpc"`
		TLS     evmserverconfig.TLSConfig     `mapstructure:"tls"`
	}

	srvCfg := serverconfig.DefaultConfig()
	evmCfg := evmserverconfig.DefaultEVMConfig()
	evmCfg.EVMChainID = 777777

	customAppConfig := CustomAppConfig{
		Config:  *srvCfg,
		EVM:     *evmCfg,
		JSONRPC: *evmserverconfig.DefaultJSONRPCConfig(),
		TLS:     *evmserverconfig.DefaultTLSConfig(),
	}

	// Preserve Cosmos SDK settings while adding the complete EVM server
	// configuration, including JSON-RPC and WebSocket defaults.
	customAppTemplate := serverconfig.DefaultConfigTemplate + evmserverconfig.DefaultEVMConfigTemplate

	return customAppTemplate, customAppConfig
}
