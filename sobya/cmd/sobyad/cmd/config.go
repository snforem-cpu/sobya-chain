package cmd

import (
	cmtcfg "github.com/cometbft/cometbft/config"
	serverconfig "github.com/cosmos/cosmos-sdk/server/config"
	evmserverconfig "github.com/cosmos/evm/server/config"
)

func initCometBFTConfig() *cmtcfg.Config {
	cfg := cmtcfg.DefaultConfig()
	cfg.RPC.ListenAddress = "tcp://127.0.0.1:26657"
	cfg.RPC.Unsafe = false
	cfg.P2P.ListenAddress = "tcp://0.0.0.0:26656"
	return cfg
}

func defaultAppConfig() *evmserverconfig.Config {
	srvCfg := serverconfig.DefaultConfig()
	// Owner-approved validator/RPC-node admission floor; distinct from EIP-1559 base fee.
	srvCfg.MinGasPrices = "1000000000asobya"
	srvCfg.Mempool.MaxTxs = 5000

	evmCfg := evmserverconfig.DefaultEVMConfig()
	evmCfg.EVMChainID = 357812033857

	jsonRPC := evmserverconfig.DefaultJSONRPCConfig()
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
	customAppTemplate := serverconfig.DefaultConfigTemplate + evmserverconfig.DefaultEVMConfigTemplate
	return customAppTemplate, defaultAppConfig()
}
