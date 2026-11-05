package cmd

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/spf13/viper"
)

func TestSyncClientChainIDFromInitializedGenesis(t *testing.T) {
	home := t.TempDir()
	configDir := filepath.Join(home, "config")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("create config directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(configDir, "client.toml"), []byte("chain-id = \"\"\nkeyring-backend = \"test\"\nnode = \"tcp://localhost:26657\"\n"), 0o600); err != nil {
		t.Fatalf("write client config fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(configDir, "genesis.json"), []byte(`{"chain_id":"sobya-prelaunch-test-1"}`), 0o600); err != nil {
		t.Fatalf("write genesis fixture: %v", err)
	}

	if err := syncClientChainIDFromGenesis(home); err != nil {
		t.Fatalf("sync client chain ID: %v", err)
	}

	v := viper.New()
	v.SetConfigFile(filepath.Join(configDir, "client.toml"))
	if err := v.ReadInConfig(); err != nil {
		t.Fatalf("read updated client.toml: %v", err)
	}
	if got := v.GetString("chain-id"); got != "sobya-prelaunch-test-1" {
		t.Fatalf("client.toml chain-id = %q, want %q", got, "sobya-prelaunch-test-1")
	}
	if got := v.GetString("keyring-backend"); got != "test" {
		t.Fatalf("existing client.toml setting was not preserved: keyring-backend = %q", got)
	}
}

func TestWriteClientChainIDCreatesDefaultClientConfig(t *testing.T) {
	home := t.TempDir()
	if err := writeClientChainID(home, "sobya-prelaunch-test-2"); err != nil {
		t.Fatalf("write client chain ID: %v", err)
	}
	v := viper.New()
	v.SetConfigFile(filepath.Join(home, "config", "client.toml"))
	if err := v.ReadInConfig(); err != nil {
		t.Fatalf("read generated client.toml: %v", err)
	}
	if got := v.GetString("chain-id"); got != "sobya-prelaunch-test-2" {
		t.Fatalf("client.toml chain-id = %q, want %q", got, "sobya-prelaunch-test-2")
	}
	if got := v.GetString("keyring-backend"); got != "os" {
		t.Fatalf("default keyring backend = %q, want os", got)
	}
}

func TestSyncClientChainIDRejectsEmptyGenesisChainID(t *testing.T) {
	home := t.TempDir()
	configDir := filepath.Join(home, "config")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("create config directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(configDir, "genesis.json"), []byte(`{"chain_id":""}`), 0o600); err != nil {
		t.Fatalf("write genesis fixture: %v", err)
	}
	if err := syncClientChainIDFromGenesis(home); err == nil {
		t.Fatal("expected an empty genesis chain ID to be rejected")
	}
}
