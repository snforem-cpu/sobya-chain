package app

import (
	"fmt"
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
	})

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

	return nil
}
