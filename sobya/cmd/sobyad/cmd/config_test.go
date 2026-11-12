package cmd

import "testing"

func TestDefaultAppConfigKeepsRPCPrivateAndLocked(t *testing.T) {
	cfg := defaultAppConfig()
	if cfg.JSONRPC.Enable {
		t.Fatal("EVM JSON-RPC must remain disabled until an operator explicitly enables it")
	}
	if cfg.JSONRPC.Address != "127.0.0.1:8545" {
		t.Fatalf("JSON-RPC address = %q, want loopback", cfg.JSONRPC.Address)
	}
	if cfg.JSONRPC.WsAddress != "127.0.0.1:8546" {
		t.Fatalf("JSON-RPC WebSocket address = %q, want loopback", cfg.JSONRPC.WsAddress)
	}
	if cfg.JSONRPC.AllowInsecureUnlock {
		t.Fatal("insecure account unlocking must be disabled")
	}
	if cfg.JSONRPC.EnableProfiling {
		t.Fatal("public EVM profiling must be disabled")
	}
	if cfg.JSONRPC.MaxOpenConnections != 100 {
		t.Fatalf("JSON-RPC max connections = %d, want 100", cfg.JSONRPC.MaxOpenConnections)
	}
	if cfg.EVM.EVMChainID != 777777 {
		t.Fatalf("development EVM chain ID changed unexpectedly: %d", cfg.EVM.EVMChainID)
	}
	if cfg.MinGasPrices != "1000000000asobya" {
		t.Fatalf("minimum gas prices = %q, want 1000000000asobya", cfg.MinGasPrices)
	}
}

func TestDefaultCometBFTConfigKeepsAdminRPCPrivate(t *testing.T) {
	cfg := initCometBFTConfig()
	if cfg.RPC.ListenAddress != "tcp://127.0.0.1:26657" {
		t.Fatalf("CometBFT RPC listener = %q, want loopback", cfg.RPC.ListenAddress)
	}
	if cfg.RPC.Unsafe {
		t.Fatal("CometBFT unsafe RPC must be disabled")
	}
	if cfg.P2P.ListenAddress != "tcp://0.0.0.0:26656" {
		t.Fatalf("CometBFT P2P listener = %q, want public-interface listener", cfg.P2P.ListenAddress)
	}
}
