package app

import (
	"fmt"

	sdk "github.com/cosmos/cosmos-sdk/types"
)

// installNativeSupplyCap verifies the committed native supply after every
// module EndBlocker has completed. This deliberately checks net block state:
// Cosmos EVM may use paired bank mint/burn operations while reconciling EVM
// account balances, so rejecting each intermediate MintCoins call can break
// a value-conserving EVM transfer when the chain is at its supply cap.
func (app *App) installNativeSupplyCap() error {
	app.SetEndBlocker(func(ctx sdk.Context) (sdk.EndBlock, error) {
		response, err := app.ModuleManager.EndBlock(ctx)
		if err != nil {
			return response, err
		}

		nativeSupply := app.BankKeeper.GetSupply(ctx, BaseDenom).Amount
		if err := validateNativeSupply(nativeSupply); err != nil {
			return response, fmt.Errorf("SOBYA native supply cap invariant failed at end of block %d: %w", ctx.BlockHeight(), err)
		}

		return response, nil
	})

	return nil
}
