package app

import sdk "github.com/cosmos/cosmos-sdk/types"

// splitTransactionFees computes the agreed SOBYA fee split without moving funds.
// Runtime fee routing must call this from a deterministic block execution hook.
// Integer rounding dust is assigned to the treasury share so the three outputs
// always add up to the exact amount collected for every denomination.
func splitTransactionFees(fees sdk.Coins) (treasury, validators, community sdk.Coins) {
	treasuryCoins := make([]sdk.Coin, 0, len(fees))
	validatorCoins := make([]sdk.Coin, 0, len(fees))
	communityCoins := make([]sdk.Coin, 0, len(fees))

	for _, fee := range fees {
		validatorShare := fee.Amount.MulRaw(30).QuoRaw(100)
		communityShare := fee.Amount.MulRaw(20).QuoRaw(100)
		treasuryShare := fee.Amount.Sub(validatorShare).Sub(communityShare)

		if !treasuryShare.IsZero() {
			treasuryCoins = append(treasuryCoins, sdk.NewCoin(fee.Denom, treasuryShare))
		}
		if !validatorShare.IsZero() {
			validatorCoins = append(validatorCoins, sdk.NewCoin(fee.Denom, validatorShare))
		}
		if !communityShare.IsZero() {
			communityCoins = append(communityCoins, sdk.NewCoin(fee.Denom, communityShare))
		}
	}

	return sdk.NewCoins(treasuryCoins...), sdk.NewCoins(validatorCoins...), sdk.NewCoins(communityCoins...)
}
