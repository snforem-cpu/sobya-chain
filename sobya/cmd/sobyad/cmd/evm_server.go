package cmd

import (
	"fmt"
	"io"

	"cosmossdk.io/log"
	dbm "github.com/cosmos/cosmos-db"
	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/client/flags"
	servertypes "github.com/cosmos/cosmos-sdk/server/types"
	evmconfig "github.com/cosmos/evm/config"
	cosmosevmserver "github.com/cosmos/evm/server"
	"github.com/spf13/cast"
	"github.com/spf13/cobra"

	"sobya/app"
)

func addEVMServerCommands(rootCmd *cobra.Command) {
	cosmosevmserver.AddCommands(
		rootCmd,
		cosmosevmserver.NewDefaultStartOptions(newEVMApp, app.DefaultNodeHome),
		exportEVMApp,
		func(*cobra.Command) {},
	)
}

func newEVMApp(logger log.Logger, db dbm.DB, traceStore io.Writer, appOpts servertypes.AppOptions) cosmosevmserver.Application {
	home := cast.ToString(appOpts.Get(flags.FlagHome))
	chainID := cast.ToString(appOpts.Get(flags.FlagChainID))
	if chainID == "" {
		var err error
		chainID, err = evmconfig.GetChainIDFromHome(home)
		if err != nil {
			panic(err)
		}
	}
	return app.New(logger, db, traceStore, true, appOpts, baseapp.SetChainID(chainID))
}

func exportEVMApp(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	height int64,
	forZeroHeight bool,
	jailAllowedAddrs []string,
	appOpts servertypes.AppOptions,
	modulesToExport []string,
) (servertypes.ExportedApp, error) {
	home, ok := appOpts.Get(flags.FlagHome).(string)
	if !ok || home == "" {
		return servertypes.ExportedApp{}, fmt.Errorf("application home not set")
	}
	chainID, err := evmconfig.GetChainIDFromHome(home)
	if err != nil {
		return servertypes.ExportedApp{}, err
	}

	loadLatest := height == -1
	evmApp := app.New(logger, db, traceStore, loadLatest, appOpts, baseapp.SetChainID(chainID))
	if height != -1 {
		if err := evmApp.LoadHeight(height); err != nil {
			return servertypes.ExportedApp{}, err
		}
	}
	return evmApp.ExportAppStateAndValidators(forZeroHeight, jailAllowedAddrs, modulesToExport)
}
