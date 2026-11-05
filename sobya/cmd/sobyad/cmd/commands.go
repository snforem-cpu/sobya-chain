package cmd

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"

	"cosmossdk.io/log"
	confixcmd "cosmossdk.io/tools/confix/cmd"
	dbm "github.com/cosmos/cosmos-db"
	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/debug"
	"github.com/cosmos/cosmos-sdk/client/flags"
	"github.com/cosmos/cosmos-sdk/client/keys"
	"github.com/cosmos/cosmos-sdk/client/pruning"
	"github.com/cosmos/cosmos-sdk/client/rpc"
	"github.com/cosmos/cosmos-sdk/client/snapshot"
	"github.com/cosmos/cosmos-sdk/server"
	cosmosevmserver "github.com/cosmos/evm/server"
	servertypes "github.com/cosmos/cosmos-sdk/server/types"
	"github.com/cosmos/cosmos-sdk/types/module"
	authcmd "github.com/cosmos/cosmos-sdk/x/auth/client/cli"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	genutilcli "github.com/cosmos/cosmos-sdk/x/genutil/client/cli"

	"sobya/app"
)

func initRootCmd(
	rootCmd *cobra.Command,
	txConfig client.TxConfig,
	basicManager module.BasicManager,
) {
	rootCmd.AddCommand(
		newInitCmd(basicManager, app.DefaultNodeHome),
		NewInPlaceTestnetCmd(),
		NewTestnetMultiNodeCmd(basicManager, banktypes.GenesisBalancesIterator{}),
		debug.Cmd(),
		confixcmd.ConfigCommand(),
		pruning.Cmd(newApp, app.DefaultNodeHome),
		snapshot.Cmd(newApp),
	)

	cosmosevmserver.AddCommands(
		rootCmd,
		cosmosevmserver.NewDefaultStartOptions(newEVMApp, app.DefaultNodeHome),
		exportEVMApp,
		addModuleInitFlags,
	)

	// add keybase, auxiliary RPC, query, genesis, and tx child commands
	rootCmd.AddCommand(
		server.StatusCommand(),
		genutilcli.Commands(txConfig, basicManager, app.DefaultNodeHome),
		queryCommand(),
		txCommand(),
		keys.Commands(),
	)
}

// addModuleInitFlags adds more flags to the start command.
// newInitCmd wraps the SDK init command and synchronizes client.toml's
// chain-id with the generated genesis.json. Cosmos EVM reads BaseApp's chain
// ID from client.toml at startup; the upstream SDK init command writes the
// genesis chain ID but leaves this client setting empty.
func newInitCmd(basicManager module.BasicManager, defaultNodeHome string) *cobra.Command {
	initCmd := genutilcli.InitCmd(basicManager, defaultNodeHome)
	originalRunE := initCmd.RunE
	initCmd.RunE = func(cmd *cobra.Command, args []string) error {
		if err := originalRunE(cmd, args); err != nil {
			return err
		}
		home, err := cmd.Flags().GetString(flags.FlagHome)
		if err != nil {
			return err
		}
		if home == "" {
			home = defaultNodeHome
		}
		return syncClientChainIDFromGenesis(home)
	}
	return initCmd
}

// syncClientChainIDFromGenesis copies the generated genesis chain ID into
// config/client.toml, which Cosmos EVM uses when constructing BaseApp.
func syncClientChainIDFromGenesis(home string) error {
	genesisPath := filepath.Join(home, "config", "genesis.json")
	genesisBytes, err := os.ReadFile(genesisPath)
	if err != nil {
		return fmt.Errorf("read initialized genesis: %w", err)
	}
	var genesis struct {
		ChainID string `json:"chain_id"`
	}
	if err := json.Unmarshal(genesisBytes, &genesis); err != nil {
		return fmt.Errorf("decode initialized genesis chain ID: %w", err)
	}
	if genesis.ChainID == "" {
		return errors.New("initialized genesis has an empty chain_id")
	}
	return writeClientChainID(home, genesis.ChainID)
}

// writeClientChainID updates client.toml without discarding existing client
// settings. If no client file exists yet, it writes the SDK's standard defaults.
func writeClientChainID(home, chainID string) error {
	if chainID == "" {
		return errors.New("cannot write an empty client chain ID")
	}
	configDir := filepath.Join(home, "config")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		return fmt.Errorf("create client config directory: %w", err)
	}
	configPath := filepath.Join(configDir, "client.toml")
	v := viper.New()
	v.SetConfigFile(configPath)
	v.SetConfigType("toml")
	if _, err := os.Stat(configPath); err == nil {
		if err := v.ReadInConfig(); err != nil {
			return fmt.Errorf("read client.toml: %w", err)
		}
	} else if os.IsNotExist(err) {
		v.Set("keyring-backend", "os")
		v.Set("keyring-default-keyname", "")
		v.Set("output", "text")
		v.Set("node", "tcp://localhost:26657")
		v.Set("broadcast-mode", "sync")
	} else {
		return fmt.Errorf("stat client.toml: %w", err)
	}
	v.Set("chain-id", chainID)
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		if err := v.WriteConfigAs(configPath); err != nil {
			return fmt.Errorf("write client.toml: %w", err)
		}
	} else if err := v.WriteConfig(); err != nil {
		return fmt.Errorf("update client.toml: %w", err)
	}
	return nil
}

func addModuleInitFlags(startCmd *cobra.Command) {
	// Cosmos EVM's start command accepts an explicit chain ID. If omitted,
	// newEVMApp reads client.toml, which sobyad init synchronizes with genesis.json.
	startCmd.Flags().String(flags.FlagChainID, "", "The network chain ID (defaults to client.toml, synchronized from genesis.json by init)")
}

func queryCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:                        "query",
		Aliases:                    []string{"q"},
		Short:                      "Querying subcommands",
		DisableFlagParsing:         false,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	cmd.AddCommand(
		rpc.WaitTxCmd(),
		rpc.ValidatorCommand(),
		server.QueryBlockCmd(),
		authcmd.QueryTxsByEventsCmd(),
		server.QueryBlocksCmd(),
		authcmd.QueryTxCmd(),
		server.QueryBlockResultsCmd(),
	)

	return cmd
}

func txCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:                        "tx",
		Short:                      "Transactions subcommands",
		DisableFlagParsing:         false,
		SuggestionsMinimumDistance: 2,
		RunE:                       client.ValidateCmd,
	}

	cmd.AddCommand(
		authcmd.GetSignCommand(),
		authcmd.GetSignBatchCommand(),
		authcmd.GetMultiSignCommand(),
		authcmd.GetMultiSignBatchCmd(),
		authcmd.GetValidateSignaturesCommand(),
		flags.LineBreak,
		authcmd.GetBroadcastCommand(),
		authcmd.GetEncodeCommand(),
		authcmd.GetDecodeCommand(),
		authcmd.GetSimulateCmd(),
	)

	return cmd
}

// newApp creates the application
func newApp(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	appOpts servertypes.AppOptions,
) servertypes.Application {
	baseappOptions := server.DefaultBaseappOptions(appOpts)

	return app.New(
		logger, db, traceStore, true,
		appOpts,
		baseappOptions...,
	)
}

// appExport creates a new app (optionally at a given height) and exports state.
func appExport(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	height int64,
	forZeroHeight bool,
	jailAllowedAddrs []string,
	appOpts servertypes.AppOptions,
	modulesToExport []string,
) (servertypes.ExportedApp, error) {
	var bApp *app.App

	// this check is necessary as we use the flag in x/upgrade.
	// we can exit more gracefully by checking the flag here.
	homePath, ok := appOpts.Get(flags.FlagHome).(string)
	if !ok || homePath == "" {
		return servertypes.ExportedApp{}, errors.New("application home not set")
	}

	viperAppOpts, ok := appOpts.(*viper.Viper)
	if !ok {
		return servertypes.ExportedApp{}, errors.New("appOpts is not viper.Viper")
	}

	appOpts = viperAppOpts
	if height != -1 {
		bApp = app.New(logger, db, traceStore, false, appOpts)
		if err := bApp.LoadHeight(height); err != nil {
			return servertypes.ExportedApp{}, err
		}
	} else {
		bApp = app.New(logger, db, traceStore, true, appOpts)
	}

	return bApp.ExportAppStateAndValidators(forZeroHeight, jailAllowedAddrs, modulesToExport)
}
