package cmd

import (
	"os"
	"path/filepath"
	"testing"

	cmtcfg "github.com/cometbft/cometbft/config"
)

func TestSyncCometBFTChainIDFromInitializedGenesis(t *testing.T) {
	home := t.TempDir()
	configDir := filepath.Join(home, "config")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("create config directory: %v", err)
	}

	cometConfig := cmtcfg.DefaultConfig()
	cometConfig.SetRoot(home)
	configPath := filepath.Join(configDir, "config.toml")
	cmtcfg.WriteConfigFile(configPath, cometConfig)

	genesisPath := filepath.Join(configDir, "genesis.json")
	if err := os.WriteFile(genesisPath, []byte(`{"chain_id":"sobya-prelaunch-test-1"}`), 0o600); err != nil {
		t.Fatalf("write genesis fixture: %v", err)
	}

	if err := syncCometBFTChainID(home); err != nil {
		t.Fatalf("sync CometBFT chain ID: %v", err)
	}

	got := cmtcfg.LoadConfigFile(configPath)
	if got.ChainID != "sobya-prelaunch-test-1" {
		t.Fatalf("config.toml chain_id = %q, want %q", got.ChainID, "sobya-prelaunch-test-1")
	}
}

func TestSyncCometBFTChainIDRejectsEmptyGenesisChainID(t *testing.T) {
	home := t.TempDir()
	configDir := filepath.Join(home, "config")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("create config directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(configDir, "genesis.json"), []byte(`{"chain_id":""}`), 0o600); err != nil {
		t.Fatalf("write genesis fixture: %v", err)
	}
	if err := syncCometBFTChainID(home); err == nil {
		t.Fatal("expected an empty genesis chain ID to be rejected")
	}
}
