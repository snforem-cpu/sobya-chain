package app

import (
	"testing"

	sdkmath "cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

func TestSplitTransactionFeesExactRatios(t *testing.T) {
	fees := sdk.NewCoins(sdk.NewCoin(BaseDenom, sdkmath.NewInt(100)))
	treasury, validators, community := splitTransactionFees(fees)

	assertFeeAmount(t, treasury, BaseDenom, 50)
	assertFeeAmount(t, validators, BaseDenom, 30)
	assertFeeAmount(t, community, BaseDenom, 20)
	assertFeeConservation(t, fees, treasury, validators, community)
}

func TestSplitTransactionFeesAssignsRoundingDustToTreasury(t *testing.T) {
	fees := sdk.NewCoins(sdk.NewCoin(BaseDenom, sdkmath.NewInt(7)))
	treasury, validators, community := splitTransactionFees(fees)

	// floor(7*30%) = 2; floor(7*20%) = 1; remainder = 4.
	assertFeeAmount(t, treasury, BaseDenom, 4)
	assertFeeAmount(t, validators, BaseDenom, 2)
	assertFeeAmount(t, community, BaseDenom, 1)
	assertFeeConservation(t, fees, treasury, validators, community)
}

func TestSplitTransactionFeesSupportsMultipleDenominations(t *testing.T) {
	fees := sdk.NewCoins(
		sdk.NewCoin(BaseDenom, sdkmath.NewInt(101)),
		sdk.NewCoin("uatom", sdkmath.NewInt(1000)),
	)
	treasury, validators, community := splitTransactionFees(fees)
	assertFeeConservation(t, fees, treasury, validators, community)
	assertFeeAmount(t, treasury, BaseDenom, 51)
	assertFeeAmount(t, validators, BaseDenom, 30)
	assertFeeAmount(t, community, BaseDenom, 20)
	assertFeeAmount(t, treasury, "uatom", 500)
	assertFeeAmount(t, validators, "uatom", 300)
	assertFeeAmount(t, community, "uatom", 200)
}

func assertFeeAmount(t *testing.T, coins sdk.Coins, denom string, expected int64) {
	t.Helper()
	if got := coins.AmountOf(denom); !got.Equal(sdkmath.NewInt(expected)) {
		t.Fatalf("%s amount = %s, want %d", denom, got, expected)
	}
}

func assertFeeConservation(t *testing.T, fees, treasury, validators, community sdk.Coins) {
	t.Helper()
	total := treasury.Add(validators...).Add(community...)
	if total.String() != fees.String() {
		t.Fatalf("fee split does not conserve funds: input=%s output=%s", fees, total)
	}
}
