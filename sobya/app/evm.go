package app

import (
	"fmt"
	"errors"

	"github.com/ethereum/go-ethereum/common"
	ethtypes "github.com/ethereum/go-ethereum/core/types"
	"cosmossdk.io/log"
	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/client"
	sdkmempool "github.com/cosmos/cosmos-sdk/types/mempool"
	evmconfig "github.com/cosmos/evm/config"
	evmmempool "github.com/cosmos/evm/mempool"

	evmante "github.com/cosmos/evm/ante"
	precompiletypes "github.com/cosmos/evm/precompiles/types"
	antetypes "github.com/cosmos/evm/ante/types"
	"strconv"

	storetypes "cosmossdk.io/store/types"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	govtypes "github.com/cosmos/cosmos-sdk/x/gov/types"
	sdk "github.com/cosmos/cosmos-sdk/types"

	evmaddress "github.com/cosmos/evm/encoding/address"
	"github.com/cosmos/evm/x/erc20"
	erc20keeper "github.com/cosmos/evm/x/erc20/keeper"
	erc20types "github.com/cosmos/evm/x/erc20/types"
	"github.com/cosmos/evm/x/feemarket"
	feemarketkeeper "github.com/cosmos/evm/x/feemarket/keeper"
	feemarkettypes "github.com/cosmos/evm/x/feemarket/types"
	"github.com/cosmos/evm/x/vm"
	evmkeeper "github.com/cosmos/evm/x/vm/keeper"
	evmwrappers "github.com/cosmos/evm/x/vm/wrappers"
	evmtypes "github.com/cosmos/evm/x/vm/types"
	servertypes "github.com/cosmos/cosmos-sdk/server/types"
)

// DefaultEVMChainID is a development default only. Operators must set a
// network-specific EVM chain ID in app.toml before creating a public genesis.
const DefaultEVMChainID uint64 = 777777

// registerEVMModules adds the Cosmos EVM stores, keepers, and application
// modules to the existing runtime.App. The SDK runtime supports this hybrid
// registration path, so the rest of SOBYA's depinject-based application stays
// intact.
func (app *App) registerEVMModules(appOpts servertypes.AppOptions) error {
	evmStoreKey := storetypes.NewKVStoreKey(evmtypes.StoreKey)
	feeMarketStoreKey := storetypes.NewKVStoreKey(feemarkettypes.StoreKey)
	erc20StoreKey := storetypes.NewKVStoreKey(erc20types.StoreKey)
	evmTransientKey := storetypes.NewTransientStoreKey(evmtypes.TransientKey)
	feeMarketTransientKey := storetypes.NewTransientStoreKey(feemarkettypes.TransientKey)

	if err := app.RegisterStores(
		evmStoreKey,
		feeMarketStoreKey,
		erc20StoreKey,
		evmTransientKey,
		feeMarketTransientKey,
	); err != nil {
		return fmt.Errorf("register Cosmos EVM stores: %w", err)
	}

	// EVM keeper uses the full KV key map for precompile/context integrations.
	storeKeys := make(map[string]*storetypes.KVStoreKey)
	for _, name := range []string{
		"acc", "bank", "staking", "mint", "distribution", "slashing", "gov",
		"consensus", "upgrade", "feegrant", "evidence", "authz", "ibc",
		"transfer", "ica", "icahost", "icacontroller", "group", "nft",
		"params", "epochs", "circuit", "vesting",
		evmtypes.StoreKey, feemarkettypes.StoreKey, erc20types.StoreKey,
	} {
		if key := app.GetKey(name); key != nil {
			storeKeys[name] = key
		}
	}

	evmChainID := DefaultEVMChainID
	if appOpts != nil {
		if raw := appOpts.Get("evm.evm-chain-id"); raw != nil {
			value := fmt.Sprint(raw)
			if value != "" && value != "0" {
				parsed, err := strconv.ParseUint(value, 10, 64)
				if err != nil || parsed == 0 {
					return fmt.Errorf("invalid evm.evm-chain-id %q: expected a positive uint64", value)
				}
				evmChainID = parsed
			}
		}
	}

	govAuthority := authtypes.NewModuleAddress(govtypes.ModuleName)
	app.FeeMarketKeeper = feemarketkeeper.NewKeeper(
		app.appCodec,
		govAuthority,
		feeMarketStoreKey,
		feeMarketTransientKey,
	)

	// SOBYA's native gas coin already has 18 decimals, so the SDK bank keeper
	// is used directly; x/precisebank is intentionally not added.
	app.EVMKeeper = evmkeeper.NewKeeper(
		app.appCodec,
		evmStoreKey,
		evmTransientKey,
		storeKeys,
		govAuthority,
		app.AuthKeeper,
		evmwrappers.NewBankWrapper(app.BankKeeper),
		app.StakingKeeper,
		app.FeeMarketKeeper,
		&app.ConsensusParamsKeeper,
		&app.Erc20Keeper,
		evmChainID,
		"",
	).WithDefaultEvmCoinInfo(evmtypes.EvmCoinInfo{
		Denom:         BaseDenom,
		ExtendedDenom: BaseDenom,
		DisplayDenom:  DisplayDenom,
		Decimals:      DisplayExponent,
	}).WithStaticPrecompiles(
		precompiletypes.DefaultStaticPrecompiles(
			*app.StakingKeeper,
			app.DistrKeeper,
			app.BankKeeper,
			&app.Erc20Keeper,
			&app.TransferKeeper,
			app.IBCKeeper.ChannelKeeper,
			*app.GovKeeper,
			app.SlashingKeeper,
			app.appCodec,
		),
	)

	app.Erc20Keeper = erc20keeper.NewKeeper(
		erc20StoreKey,
		app.appCodec,
		govAuthority,
		app.AuthKeeper,
		app.BankKeeper,
		app.EVMKeeper,
		app.StakingKeeper,
		&app.TransferKeeper,
	)

	if err := app.RegisterModules(
		vm.NewAppModule(
			app.EVMKeeper,
			app.AuthKeeper,
			app.BankKeeper,
			evmaddress.NewEvmCodec(sdk.GetConfig().GetBech32AccountAddrPrefix()),
		),
		feemarket.NewAppModule(app.FeeMarketKeeper),
		erc20.NewAppModule(app.Erc20Keeper, app.AuthKeeper),
	); err != nil {
		return fmt.Errorf("register Cosmos EVM modules: %w", err)
	}

	// Route both Ethereum and Cosmos SDK transactions through Cosmos EVM\x27s
	// transaction-aware ante handler. This is essential: keeper/module wiring
	// alone does not make signed Ethereum transactions executable.
	anteOptions := evmante.HandlerOptions{
		Cdc:                    app.appCodec,
		AccountKeeper:          app.AuthKeeper,
		BankKeeper:             app.BankKeeper,
		IBCKeeper:              app.IBCKeeper,
		FeeMarketKeeper:        app.FeeMarketKeeper,
		EvmKeeper:              app.EVMKeeper,
		FeegrantKeeper:         app.FeeGrantKeeper,
		ExtensionOptionChecker: antetypes.HasDynamicFeeExtensionOption,
		SignModeHandler:        app.txConfig.SignModeHandler(),
		SigGasConsumer:         evmante.SigVerificationGasConsumer,
		DynamicFeeChecker:      true,
		PendingTxListener:      app.onPendingTx,
	}
	if err := anteOptions.Validate(); err != nil {
		return fmt.Errorf("validate Cosmos EVM ante handler options: %w", err)
	}
	app.SetAnteHandler(evmante.NewAnteHandler(anteOptions))

	if err := app.configureEVMMempool(appOpts, app.Logger()); err != nil {
		return fmt.Errorf("configure Cosmos EVM mempool: %w", err)
	}

	return nil
}


// configureEVMMempool installs the unified Ethereum/Cosmos transaction pool,
// CheckTx validation, and proposal handlers before BaseApp is loaded/sealed.
func (app *App) configureEVMMempool(appOpts servertypes.AppOptions, logger log.Logger) error {
	if evmtypes.GetChainConfig() == nil {
		return fmt.Errorf("Cosmos EVM chain configuration is not initialized")
	}

	cosmosPoolMaxTx := evmconfig.GetCosmosPoolMaxTx(appOpts, logger)
	if cosmosPoolMaxTx < 0 {
		return fmt.Errorf("Cosmos EVM mempool is disabled; JSON-RPC requires the EVM mempool")
	}

	mempoolConfig := &evmmempool.EVMMempoolConfig{
		AnteHandler:      app.BaseApp.AnteHandler(),
		LegacyPoolConfig: evmconfig.GetLegacyPoolConfig(appOpts, logger),
		BlockGasLimit:    evmconfig.GetBlockGasLimit(appOpts, logger),
		MinTip:           evmconfig.GetMinTip(appOpts, logger),
		BroadCastTxFn: func(txs []*ethtypes.Transaction) error {
			return broadcastEVMTransactions(app.clientCtx, app.txConfig, txs)
		},
	}

	pool := evmmempool.NewExperimentalEVMMempool(
		app.CreateQueryContext,
		logger,
		app.EVMKeeper,
		app.FeeMarketKeeper,
		app.txConfig,
		app.clientCtx,
		mempoolConfig,
		cosmosPoolMaxTx,
	)
	app.EVMMempool = pool
	app.SetMempool(pool)
	app.SetCheckTxHandler(evmmempool.NewCheckTxHandler(pool))

	proposalHandler := baseapp.NewDefaultProposalHandler(pool, app)
	proposalHandler.SetSignerExtractionAdapter(
		evmmempool.NewEthSignerExtractionAdapter(
			sdkmempool.NewDefaultSignerExtractionAdapter(),
		),
	)
	app.SetPrepareProposal(proposalHandler.PrepareProposalHandler())
	app.SetProcessProposal(proposalHandler.ProcessProposalHandler())

	return nil
}

// GetMempool exposes the unified EVM/Cosmos mempool to the Cosmos EVM server.
func (app *App) GetMempool() sdkmempool.ExtMempool {
	return app.EVMMempool
}

// GetAnteHandler exposes the active transaction ante handler to the EVM mempool.
func (app *App) GetAnteHandler() sdk.AnteHandler {
	return app.BaseApp.AnteHandler()
}

// SetClientCtx provides the RPC client context used by the EVM mempool broadcaster.
func (app *App) SetClientCtx(clientCtx client.Context) {
	app.clientCtx = clientCtx
}

// RegisterPendingTxListener registers listeners used by the Ethereum JSON-RPC pending stream.
func (app *App) RegisterPendingTxListener(listener func(common.Hash)) {
	app.pendingTxListeners = append(app.pendingTxListeners, listener)
}

func (app *App) onPendingTx(hash common.Hash) {
	for _, listener := range app.pendingTxListeners {
		listener(hash)
	}
}

// Close shuts down the EVM transaction pool before closing BaseApp.
func (app *App) Close() error {
	var poolErr error
	if app.EVMMempool != nil {
		poolErr = app.EVMMempool.Close()
	}
	return errors.Join(poolErr, app.App.Close())
}

// broadcastEVMTransactions wraps signed Ethereum transactions as MsgEthereumTx
// and broadcasts them through the client context supplied by the EVM server.
func broadcastEVMTransactions(clientCtx client.Context, txConfig client.TxConfig, ethTxs []*ethtypes.Transaction) error {
	for _, ethTx := range ethTxs {
		msg := &evmtypes.MsgEthereumTx{}
		msg.FromEthereumTx(ethTx)
		txBuilder := txConfig.NewTxBuilder()
		if err := txBuilder.SetMsgs(msg); err != nil {
			return fmt.Errorf("set Ethereum message: %w", err)
		}
		txBytes, err := txConfig.TxEncoder()(txBuilder.GetTx())
		if err != nil {
			return fmt.Errorf("encode Ethereum transaction: %w", err)
		}
		res, err := clientCtx.BroadcastTxSync(txBytes)
		if err != nil {
			return fmt.Errorf("broadcast Ethereum transaction %s: %w", ethTx.Hash().Hex(), err)
		}
		if res.Code != 0 {
			return fmt.Errorf("Ethereum transaction %s rejected: code=%d log=%s", ethTx.Hash().Hex(), res.Code, res.RawLog)
		}
	}
	return nil
}
