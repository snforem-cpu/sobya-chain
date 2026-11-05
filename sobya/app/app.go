package app

import (
	"encoding/json"
	"fmt"
	"io"

	clienthelpers "cosmossdk.io/client/v2/helpers"
	"cosmossdk.io/core/address"
	"cosmossdk.io/core/appmodule"
	"cosmossdk.io/depinject"
	"cosmossdk.io/log"
	"cosmossdk.io/x/tx/signing"
	feegrantkeeper "cosmossdk.io/x/feegrant/keeper"
	storetypes "cosmossdk.io/store/types"
	circuitkeeper "cosmossdk.io/x/circuit/keeper"
	upgradekeeper "cosmossdk.io/x/upgrade/keeper"

	abci "github.com/cometbft/cometbft/abci/types"
	"github.com/ethereum/go-ethereum/common"
	evmmempool "github.com/cosmos/evm/mempool"
	dbm "github.com/cosmos/cosmos-db"
	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/client"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/cosmos-sdk/runtime"
	"github.com/cosmos/cosmos-sdk/server"
	"github.com/cosmos/cosmos-sdk/server/api"
	"github.com/cosmos/cosmos-sdk/server/config"
	servertypes "github.com/cosmos/cosmos-sdk/server/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/module"
	"github.com/cosmos/cosmos-sdk/x/auth"
	evmaddress "github.com/cosmos/evm/encoding/address"
	erc20keeper "github.com/cosmos/evm/x/erc20/keeper"
	feemarketkeeper "github.com/cosmos/evm/x/feemarket/keeper"
	evmkeeper "github.com/cosmos/evm/x/vm/keeper"
	evmtypes "github.com/cosmos/evm/x/vm/types"
	erc20types "github.com/cosmos/evm/x/erc20/types"
	feemarkettypes "github.com/cosmos/evm/x/feemarket/types"
	erc20module "github.com/cosmos/evm/x/erc20"
	feemarketmodule "github.com/cosmos/evm/x/feemarket"
	authkeeper "github.com/cosmos/cosmos-sdk/x/auth/keeper"
	authsims "github.com/cosmos/cosmos-sdk/x/auth/simulation"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	authzkeeper "github.com/cosmos/cosmos-sdk/x/authz/keeper"
	bankkeeper "github.com/cosmos/cosmos-sdk/x/bank/keeper"
	consensuskeeper "github.com/cosmos/cosmos-sdk/x/consensus/keeper"
	distrkeeper "github.com/cosmos/cosmos-sdk/x/distribution/keeper"
	"github.com/cosmos/cosmos-sdk/x/genutil"
	genutiltypes "github.com/cosmos/cosmos-sdk/x/genutil/types"
	govkeeper "github.com/cosmos/cosmos-sdk/x/gov/keeper"
	mintkeeper "github.com/cosmos/cosmos-sdk/x/mint/keeper"
	paramskeeper "github.com/cosmos/cosmos-sdk/x/params/keeper"
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
	slashingkeeper "github.com/cosmos/cosmos-sdk/x/slashing/keeper"
	stakingkeeper "github.com/cosmos/cosmos-sdk/x/staking/keeper"
	icacontrollerkeeper "github.com/cosmos/ibc-go/v10/modules/apps/27-interchain-accounts/controller/keeper"
	icahostkeeper "github.com/cosmos/ibc-go/v10/modules/apps/27-interchain-accounts/host/keeper"
	ibctransferkeeper "github.com/cosmos/ibc-go/v10/modules/apps/transfer/keeper"
	ibckeeper "github.com/cosmos/ibc-go/v10/modules/core/keeper"

	"sobya/docs"
)

const (
	// Name is the name of the application.
	Name = "sobya"
	// AccountAddressPrefix is the prefix for accounts addresses.
	AccountAddressPrefix = "sobya"
	// ChainCoinType is the coin type of the chain.
	ChainCoinType = 118
)

// DefaultNodeHome default home directories for the application daemon
var DefaultNodeHome string

var (
	_ runtime.AppI            = (*App)(nil)
	_ servertypes.Application = (*App)(nil)
)

// App extends an ABCI application, but with most of its parameters exported.
// They are exported for convenience in creating helper functions, as object
// capabilities aren't needed for testing.
type App struct {
	*runtime.App
	legacyAmino       *codec.LegacyAmino
	appCodec          codec.Codec
	txConfig          client.TxConfig
	interfaceRegistry codectypes.InterfaceRegistry

	// keepers
	// only keepers required by the app are exposed
	// the list of all modules is available in the app_config
	AuthKeeper            authkeeper.AccountKeeper
	BankKeeper            bankkeeper.Keeper
	StakingKeeper         *stakingkeeper.Keeper
	SlashingKeeper        slashingkeeper.Keeper
	MintKeeper            mintkeeper.Keeper
	DistrKeeper           distrkeeper.Keeper
	validatorReserveStoreKey *storetypes.KVStoreKey
	GovKeeper             *govkeeper.Keeper
	UpgradeKeeper         *upgradekeeper.Keeper
	AuthzKeeper           authzkeeper.Keeper
	ConsensusParamsKeeper consensuskeeper.Keeper
	CircuitBreakerKeeper  circuitkeeper.Keeper
	ParamsKeeper          paramskeeper.Keeper

	// Cosmos EVM server state.
	clientCtx          client.Context
	EVMMempool         *evmmempool.ExperimentalEVMMempool
	pendingTxListeners []func(common.Hash)
	evmBroadcast      *evmBroadcastState

	// Cosmos EVM keepers. SOBYA uses its native 18-decimal asobya bank coin.
	FeeMarketKeeper feemarketkeeper.Keeper
	FeeGrantKeeper feegrantkeeper.Keeper
	EVMKeeper       *evmkeeper.Keeper
	Erc20Keeper     erc20keeper.Keeper

	// ibc keepers
	IBCKeeper           *ibckeeper.Keeper
	ICAControllerKeeper icacontrollerkeeper.Keeper
	ICAHostKeeper       icahostkeeper.Keeper
	TransferKeeper      ibctransferkeeper.Keeper

	// simulation manager
	sm *module.SimulationManager
}

func init() {
	var err error
	clienthelpers.EnvPrefix = Name
	DefaultNodeHome, err = clienthelpers.GetNodeHomeDirectory("." + Name)
	if err != nil {
		panic(err)
	}
}

// AppConfig returns the default app config.
func AppConfig() depinject.Config {
	return depinject.Configs(
		appConfig,
		depinject.Supply(
			// Supply basics for modules registered outside depinject as well.
			// These basics are used by init, multi-node, and genesis export
			// to create a complete app_state. Registering only runtime AppModules
			// is insufficient: their genesis sections would otherwise be absent.
			map[string]module.AppModuleBasic{
				genutiltypes.ModuleName:   genutil.NewAppModuleBasic(genutiltypes.DefaultMessageValidator),
				evmtypes.ModuleName:       EVMAppModuleBasic(),
				feemarkettypes.ModuleName: feemarketmodule.AppModuleBasic{},
				erc20types.ModuleName:     erc20module.AppModuleBasic{},
			},
		),
		// The SDK runtime collects CustomGetSigner providers and passes them
		// to ProvideInterfaceRegistry. MsgEthereumTx has no protobuf signer
		// annotation, so it must be registered through this supported DI hook.
		// MsgConvertERC20 is intentionally omitted: its protobuf descriptor
		// already declares its signer and a second extractor would be duplicate.
		depinject.Provide(ProvideEVMCustomGetSigner, ProvideEVMAddressCodecFactories),
	)
}

// New returns a reference to an initialized App.
func New(
	logger log.Logger,
	db dbm.DB,
	traceStore io.Writer,
	loadLatest bool,
	appOpts servertypes.AppOptions,
	baseAppOptions ...func(*baseapp.BaseApp),
) *App {
	var (
		app        = &App{}
		appBuilder *runtime.AppBuilder

		// merge the AppConfig and other configuration in one config
		appConfig = depinject.Configs(
			AppConfig(),
			depinject.Supply(
				appOpts, // supply app options
				logger,  // supply logger

				// Supply with IBC keeper getter for the IBC modules with App Wiring.
				// The IBC Keeper cannot be passed because it has not been initiated yet.
				// Passing the getter, the app IBC Keeper will always be accessible.
				// This needs to be removed after IBC supports App Wiring.
				app.GetIBCKeeper,

				// SOBYA has a fixed native supply. Replace the SDK mint function
				// with a no-op so parameter changes cannot re-enable token issuance.
				mintkeeper.MintFn(func(_ sdk.Context, _ *mintkeeper.Keeper) error {
					return nil
				}),

				// here alternative options can be supplied to the DI container.
				// those options can be used f.e to override the default behavior of some modules.
				// for instance supplying a custom address codec for not using bech32 addresses.
				// read the depinject documentation and depinject module wiring for more information
				// on available options and how to use them.
			),
		)
	)

	var appModules map[string]appmodule.AppModule
	if err := depinject.Inject(appConfig,
		&appBuilder,
		&appModules,
		&app.appCodec,
		&app.legacyAmino,
		&app.txConfig,
		&app.interfaceRegistry,
		&app.AuthKeeper,
		&app.BankKeeper,
		&app.StakingKeeper,
		&app.SlashingKeeper,
		&app.MintKeeper,
		&app.DistrKeeper,
		&app.GovKeeper,
		&app.UpgradeKeeper,
		&app.AuthzKeeper,
		&app.ConsensusParamsKeeper,
		&app.CircuitBreakerKeeper,
		&app.ParamsKeeper,
		&app.FeeGrantKeeper,
	); err != nil {
		panic(err)
	}

	// Cosmos EVM modules are registered manually after runtime app wiring.
	// Register their protobuf interfaces on the same registry used by appCodec
	// and txConfig, otherwise committed MsgEthereumTx envelopes cannot be
	// decoded by eth_getTransactionReceipt / transaction lookup RPC methods.
	evmtypes.RegisterInterfaces(app.interfaceRegistry)

	// Keep canonical FinalizeBlock execution synchronous. Optimistic execution
	// produced state-hash mismatches against CometBFT's requested block execution
	// in the multi-validator EVM localnet (BaseApp logged "OE aborted due to
	// hash mismatch" at matching heights). Do not enable SetOptimisticExecution
	// until the EVM/application execution path has a deterministic OE regression
	// test proving speculative and canonical app hashes are identical.

	// Build the application and mount the persistent validator-reserve store before loading state.
	app.validatorReserveStoreKey = storetypes.NewKVStoreKey(validatorReserveStoreKeyName)
	app.App = appBuilder.Build(db, traceStore, baseAppOptions...)
	app.MountKVStores(map[string]*storetypes.KVStoreKey{
		validatorReserveStoreKeyName: app.validatorReserveStoreKey,
	})

	// runtime.AppBuilder creates BaseApp with a nil transaction decoder. Install
	// the app-wired TxConfig explicitly so Ethereum MsgEthereumTx envelopes are
	// decoded and encoded by the same registry used by the EVM ante handler.
	app.SetTxDecoder(app.txConfig.TxDecoder())
	app.SetTxEncoder(app.txConfig.TxEncoder())

	// register legacy modules
	if err := app.registerIBCModules(appOpts); err != nil {
		panic(err)
	}
	if err := app.registerEVMModules(appOpts); err != nil {
		panic(err)
	}

	// Install deterministic fee routing before the first block is loaded.
	// The wrapper runs the configured module pre-blockers, then moves the
	// treasury/community shares before x/distribution consumes fee_collector.
	if err := app.installFeeRouter(); err != nil {
		panic(err)
	}
	if err := app.installValidatorReserve(); err != nil {
		panic(err)
	}
	if err := app.installNativeSupplyCap(); err != nil {
		panic(err)
	}

	/****  Module Options ****/

	// create the simulation manager and define the order of the modules for deterministic simulations
	overrideModules := map[string]module.AppModuleSimulation{
		authtypes.ModuleName: auth.NewAppModule(app.appCodec, app.AuthKeeper, authsims.RandomGenesisAccounts, nil),
	}
	app.sm = module.NewSimulationManagerFromAppModules(app.ModuleManager.Modules, overrideModules)

	app.sm.RegisterStoreDecoders()

	// A custom InitChainer sets if extra pre-init-genesis logic is required.
	// This is necessary for manually registered modules that do not support app wiring.
	// Manually set the module version map as shown below.
	// The upgrade module will automatically handle de-duplication of the module version map.
	app.SetInitChainer(func(ctx sdk.Context, req *abci.RequestInitChain) (*abci.ResponseInitChain, error) {
		if err := app.UpgradeKeeper.SetModuleVersionMap(ctx, app.ModuleManager.GetVersionMap()); err != nil {
			return nil, err
		}

		// Normalize and validate the native SOBYA denomination before any module
		// initializes its genesis state. This also enforces the native supply cap.
		normalizedGenesis, err := prepareGenesisState(app.appCodec, req.AppStateBytes)
		if err != nil {
			return nil, err
		}
		var normalizedState map[string]json.RawMessage
		if err := json.Unmarshal(normalizedGenesis, &normalizedState); err != nil {
			return nil, fmt.Errorf("decode normalized application genesis: %w", err)
		}
		req.AppStateBytes = normalizedGenesis

		response, err := app.App.InitChainer(ctx, req)
		if err != nil {
			return nil, err
		}
		if err := app.initValidatorReserveGenesis(ctx, normalizedState[validatorReserveGenesisKey]); err != nil {
			return nil, err
		}
		return response, nil
	})

	if err := app.Load(loadLatest); err != nil {
		panic(err)
	}

	return app
}

// GetSubspace returns a param subspace for a given module name.
func (app *App) GetSubspace(moduleName string) paramstypes.Subspace {
	subspace, _ := app.ParamsKeeper.GetSubspace(moduleName)
	return subspace
}

// LegacyAmino returns App's amino codec.
func (app *App) LegacyAmino() *codec.LegacyAmino {
	return app.legacyAmino
}

// AppCodec returns App's app codec.
func (app *App) AppCodec() codec.Codec {
	return app.appCodec
}

// InterfaceRegistry returns App's InterfaceRegistry.
func (app *App) InterfaceRegistry() codectypes.InterfaceRegistry {
	return app.interfaceRegistry
}

// TxConfig returns App's TxConfig
func (app *App) TxConfig() client.TxConfig {
	return app.txConfig
}

// GetKey returns the KVStoreKey for the provided store key.
func (app *App) GetKey(storeKey string) *storetypes.KVStoreKey {
	kvStoreKey, ok := app.UnsafeFindStoreKey(storeKey).(*storetypes.KVStoreKey)
	if !ok {
		return nil
	}
	return kvStoreKey
}

// SimulationManager implements the SimulationApp interface
func (app *App) SimulationManager() *module.SimulationManager {
	return app.sm
}

// RegisterAPIRoutes registers all application module routes with the provided
// API server.
func (app *App) RegisterAPIRoutes(apiSvr *api.Server, apiConfig config.APIConfig) {
	app.App.RegisterAPIRoutes(apiSvr, apiConfig)
	// register swagger API in app.go so that other applications can override easily
	if err := server.RegisterSwaggerAPI(apiSvr.ClientCtx, apiSvr.Router, apiConfig.Swagger); err != nil {
		panic(err)
	}

	// register app's OpenAPI routes.
	docs.RegisterOpenAPIService(Name, apiSvr.Router)
}

// GetMaccPerms returns a copy of the module account permissions
//
// NOTE: This is solely to be used for testing purposes.
func GetMaccPerms() map[string][]string {
	dup := make(map[string][]string)
	for _, perms := range moduleAccPerms {
		dup[perms.GetAccount()] = perms.GetPermissions()
	}
	return dup
}

// BlockedAddresses returns all the app's blocked account addresses.
func BlockedAddresses() map[string]bool {
	result := make(map[string]bool)

	if len(blockAccAddrs) > 0 {
		for _, addr := range blockAccAddrs {
			result[addr] = true
		}
	} else {
		for addr := range GetMaccPerms() {
			result[addr] = true
		}
	}

	return result
}

// ProvideEVMAddressCodecFactories makes the SDK signing context use Ethereum-compatible
// hex/bech32 codecs for account, validator, and consensus addresses.
func ProvideEVMAddressCodecFactories() (
	func() address.Codec,
	func() runtime.ValidatorAddressCodec,
	func() runtime.ConsensusAddressCodec,
) {
	return func() address.Codec {
		return evmaddress.NewEvmCodec(sdk.GetConfig().GetBech32AccountAddrPrefix())
	}, func() runtime.ValidatorAddressCodec {
		return evmaddress.NewEvmCodec(sdk.GetConfig().GetBech32ValidatorAddrPrefix())
	}, func() runtime.ConsensusAddressCodec {
		return evmaddress.NewEvmCodec(sdk.GetConfig().GetBech32ConsensusAddrPrefix())
	}
}

// ProvideEVMCustomGetSigner registers the Ethereum transaction signer
// with the Cosmos SDK runtime's InterfaceRegistry provider.
func ProvideEVMCustomGetSigner() signing.CustomGetSigner {
	return evmtypes.MsgEthereumTxCustomGetSigner
}
