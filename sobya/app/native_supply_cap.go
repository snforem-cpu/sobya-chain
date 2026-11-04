package app

import (
	"fmt"

	sdkmath "cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// installNativeSupplyCap verifies the committed native supply after every
// module EndBlocker has completed. This deliberately checks net block state:
// Cosmos EVM may use paired bank mint/burn operations while reconciling EVM
// account balances, so rejecting each intermediate MintCoins call can break
// a value-conserving EVM transfer when the chain is at its supply cap.
func validateNativeSupplyAtEndBlock(supply sdkmath.Int, height int64) error {
	if err := validateNativeSupply(supply); err != nil {
		return fmt.Errorf("SOBYA native supply cap invariant failed at end of block %d: %w", height, err)
	}
	return nil
}

func (app *App) installNativeSupplyCap() error {
	app.SetEndBlocker(func(ctx sdk.Context) (sdk.EndBlock, error) {
		response, err := app.ModuleManager.EndBlock(ctx)
		if err != nil {
			return response, err
		}

		nativeSupply := app.BankKeeper.GetSupply(ctx, BaseDenom).Amount
		if err := validateNativeSupplyAtEndBlock(nativeSupply, ctx.BlockHeight()); err != nil {
			return response, err
		}

		return response, nil
	})

	return nil
}
