package cmd

import (
	"os"

	"cosmossdk.io/client/v2/autocli"
	"cosmossdk.io/depinject"
	"cosmossdk.io/log"
	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/client/config"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/cosmos-sdk/server"
	"github.com/cosmos/cosmos-sdk/types/module"
	"github.com/cosmos/cosmos-sdk/x/auth/tx"
	authtxconfig "github.com/cosmos/cosmos-sdk/x/auth/tx/config"
	"github.com/cosmos/cosmos-sdk/x/auth/types"
	evmhd evmcryptocodec "github.com/cosmos/evm/crypto/codec"
	"github.com/cosmos/evm/crypto/hd"
	evmtypes "github.com/cosmos/evm/x/vm/types"
erc20module "github.com/cosmos/evm/x/erc20"
erc20types "github.com/cosmos/evm/x/erc20/types"
feemarketmodule "github.com/cosmos/evm/x/feemarket"
feemarkettypes "github.com/cosmos/evm/x/feemarket/types"
	"github.com/spf13/cobra"

	"sobya/app"
)

// NewRootCmd creates a new root command for sobyad. It is called once in the main function.
func NewRootCmd() *cobra.Command {
	var (
		autoCliOpts        autocli.AppOptions
		moduleBasicManager module.BasicManager
		clientCtx          client.Context
	)

	if err := depinject.Inject(
		depinject.Configs(app.AppConfig(),
			depinject.Supply(log.NewNopLogger()),
			depinject.Provide(
				ProvideClientContext,
			),
		),
		&autoCliOpts,
		&moduleBasicManager,
		&clientCtx,
	); err != nil {
		panic(err)
	}

	// Cosmos EVM modules are registered manually in the application runtime,
	// so depinject cannot discover their AppModuleBasic implementations.
	// Add them to the CLI module manager explicitly; init and multi-node use
	// this manager to construct every module's default genesis state.
	moduleBasicManager[evmtypes.ModuleName] = app.EVMAppModuleBasic()
	moduleBasicManager[feemarkettypes.ModuleName] = feemarketmodule.AppModuleBasic{}
	moduleBasicManager[erc20types.ModuleName] = erc20module.AppModuleBasic{}

	rootCmd := &cobra.Command{
		Use:           app.Name + "d",
		Short:         "sobya node",
		SilenceErrors: true,
		PersistentPreRunE: func(cmd *cobra.Command, _ []string) error {
			// set the default command outputs
			cmd.SetOut(cmd.OutOrStdout())
			cmd.SetErr(cmd.ErrOrStderr())

			clientCtx = clientCtx.WithCmdContext(cmd.Context()).WithViper(app.Name)
			clientCtx, err := client.ReadPersistentCommandFlags(clientCtx, cmd.Flags())
			if err != nil {
				return err
			}

			clientCtx, err = config.ReadFromClientConfig(clientCtx)
			if err != nil {
				return err
			}

			if err := client.SetCmdClientContextHandler(clientCtx, cmd); err != nil {
				return err
			}

			customAppTemplate, customAppConfig := initAppConfig()
			customCMTConfig := initCometBFTConfig()

			return server.InterceptConfigsPreRunHandler(cmd, customAppTemplate, customAppConfig, customCMTConfig)
		},
	}

	// Since the IBC modules don't support dependency injection, we need to
	// manually register the modules on the client side.
	// This needs to be removed after IBC supports App Wiring.
	ibcModules := app.RegisterIBC(clientCtx.Codec)
	for name, mod := range ibcModules {
		moduleBasicManager[name] = module.CoreAppModuleBasicAdaptor(name, mod)
		autoCliOpts.Modules[name] = mod
	}

	initRootCmd(rootCmd, clientCtx.TxConfig, moduleBasicManager)

	if err := autoCliOpts.EnhanceRootCommand(rootCmd); err != nil {
		panic(err)
	}

	return rootCmd
}

// registerEVMKeyringInterfaces adds Cosmos EVM's concrete account key types to
// the protobuf Any registry used by the CLI keyring. The SDK's standard
// registry does not include eth_secp256k1 by itself.
func registerEVMKeyringInterfaces(registry codectypes.InterfaceRegistry) {
	evmcryptocodec.RegisterInterfaces(registry)
}

// ProvideClientContext creates and provides a fully initialized client.Context,
// allowing it to be used for dependency injection and CLI operations.
func ProvideClientContext(
	appCodec codec.Codec,
	interfaceRegistry codectypes.InterfaceRegistry,
	txConfigOpts tx.ConfigOptions,
	legacyAmino *codec.LegacyAmino,
) client.Context {
	// The CLI/server client context is built by a separate depinject pass from
	// the running App. Register Cosmos EVM protobuf messages on this registry
	// before constructing its TxConfig; the EVM JSON-RPC transaction decoder
	// uses this client TxConfig when querying committed Ethereum transactions.
	evmtypes.RegisterInterfaces(interfaceRegistry)

	clientCtx := client.Context{}.
		WithCodec(appCodec).
		WithInterfaceRegistry(interfaceRegistry).
		WithLegacyAmino(legacyAmino).
		WithInput(os.Stdin).
		WithAccountRetriever(types.AccountRetriever{}).
		WithHomeDir(app.DefaultNodeHome).
		WithViper(app.Name) // env variable prefix

	// Read the config again to overwrite the default values with the values from the config file
	clientCtx, _ = config.ReadFromClientConfig(clientCtx)

	// textual is enabled by default, we need to re-create the tx config grpc instead of bank keeper.
	txConfigOpts.TextualCoinMetadataQueryFn = authtxconfig.NewGRPCCoinMetadataQueryFn(clientCtx)
	txConfig, err := tx.NewTxConfigWithOptions(clientCtx.Codec, txConfigOpts)
	if err != nil {
		panic(err)
	}
	clientCtx = clientCtx.WithTxConfig(txConfig).WithKeyringOptions(evmhd.EthSecp256k1Option()).WithLedgerHasProtobuf(true)

	return clientCtx
}
