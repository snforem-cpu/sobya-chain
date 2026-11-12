package app

import (
	"fmt"

	abci "github.com/cometbft/cometbft/abci/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	evmaddress "github.com/cosmos/evm/encoding/address"
)

const sharedFeeWallet = "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f"

// splitCollectedFeesForRouting sends the treasury and community portions to
// the shared management wallet. The remaining 30% stays in fee_collector for
// the standard distribution module to allocate to validators and delegators.
func splitCollectedFeesForRouting(fees sdk.Coins) (sharedWallet, validators, treasury, community sdk.Coins) {
	treasury, validators, community = splitTransactionFees(fees)
	return treasury.Add(community...), validators, treasury, community
}

// installFeeRouter wraps the runtime module pre-blocker. It executes the
// configured module pre-blockers first, then routes fees before x/distribution's
// BeginBlocker drains fee_collector. The operation is deterministic and runs
// against consensus state; a transfer error aborts block finalization.
func (app *App) installFeeRouter() error {
	addressCodec := evmaddress.NewEvmCodec(sdk.GetConfig().GetBech32AccountAddrPrefix())
	addressBytes, err := addressCodec.StringToBytes(sharedFeeWallet)
	if err != nil {
		return fmt.Errorf("decode SOBYA shared fee wallet: %w", err)
	}
	if len(addressBytes) != 20 {
		return fmt.Errorf("SOBYA shared fee wallet must decode to 20 bytes, got %d", len(addressBytes))
	}
	recipient := sdk.AccAddress(addressBytes)

	app.SetPreBlocker(func(ctx sdk.Context, req *abci.RequestFinalizeBlock) (*sdk.ResponsePreBlock, error) {
		response, err := app.App.PreBlocker(ctx, req)
		if err != nil {
			return nil, err
		}

		feeCollector := authtypes.NewModuleAddress(authtypes.FeeCollectorName)
		collected := app.BankKeeper.GetAllBalances(ctx, feeCollector)
		if len(collected) > 0 {
			sharedAmount, validatorAmount, treasuryAmount, communityAmount := splitCollectedFeesForRouting(collected)
			if len(sharedAmount) > 0 {
				if err := app.BankKeeper.SendCoinsFromModuleToAccount(
					ctx,
					authtypes.FeeCollectorName,
					recipient,
					sharedAmount,
				); err != nil {
					return nil, fmt.Errorf("route SOBYA treasury/community fees to shared wallet: %w", err)
				}
			}

			ctx.EventManager().EmitEvent(sdk.NewEvent(
				"sobya_fee_split",
				sdk.NewAttribute("shared_wallet", sharedFeeWallet),
				sdk.NewAttribute("shared_wallet_amount", sharedAmount.String()),
				sdk.NewAttribute("treasury_amount", treasuryAmount.String()),
				sdk.NewAttribute("community_amount", communityAmount.String()),
				sdk.NewAttribute("validator_amount", validatorAmount.String()),
			))
		}

		if err := app.processValidatorReserve(ctx, req); err != nil {
			return nil, fmt.Errorf("process SOBYA validator reserve: %w", err)
		}

		return response, nil
	})

	return nil
}
