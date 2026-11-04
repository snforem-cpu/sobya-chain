package app

import (
	"bytes"
	"math/big"
	"testing"
	"time"

	"cosmossdk.io/log"
	storetypes "cosmossdk.io/store/types"
	cmtproto "github.com/cometbft/cometbft/proto/tendermint/types"
	"github.com/cosmos/cosmos-sdk/baseapp"
	sdk "github.com/cosmos/cosmos-sdk/types"
	dbm "github.com/cosmos/cosmos-db"
)

func TestValidatorReserveEligibilityThreshold(t *testing.T) {
	tests := []struct {
		name string
		expected, signed uint64
		want bool
	}{
		{"exactly 95 percent", 100, 95, true},
		{"above 95 percent", 1000, 999, true},
		{"below 95 percent", 100, 94, false},
		{"zero expected", 0, 0, false},
		{"impossible signed count", 100, 101, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := validatorReserveEligible(tt.expected, tt.signed); got != tt.want {
				t.Fatalf("validatorReserveEligible(%d,%d)=%v, want %v", tt.expected, tt.signed, got, tt.want)
			}
		})
	}
}

func TestValidatorReservePayoutsArePowerWeightedAndDoNotRedistributeIneligibleShare(t *testing.T) {
	budget := big.NewInt(1000)
	stats := map[string]validatorReserveStats{
		"eligible-a": {Expected: 100, Signed: 100, PowerSum: "100"},
		"eligible-b": {Expected: 100, Signed: 95, PowerSum: "300"},
		"ineligible": {Expected: 100, Signed: 94, PowerSum: "600"},
	}
	payouts := calculateValidatorReservePayouts(budget, stats)
	if got := payouts["eligible-a"].String(); got != "100" {
		t.Fatalf("eligible-a payout=%s, want 100", got)
	}
	if got := payouts["eligible-b"].String(); got != "300" {
		t.Fatalf("eligible-b payout=%s, want 300", got)
	}
	if _, ok := payouts["ineligible"]; ok {
		t.Fatal("ineligible validator must not receive a payout")
	}
	total := new(big.Int).Add(payouts["eligible-a"], payouts["eligible-b"])
	if total.String() != "400" {
		t.Fatalf("paid=%s, want 400; ineligible share must remain in reserve", total)
	}
}

func TestValidatorReservePayoutRoundingNeverExceedsBudget(t *testing.T) {
	budget := big.NewInt(10)
	stats := map[string]validatorReserveStats{
		"a": {Expected: 100, Signed: 100, PowerSum: "1"},
		"b": {Expected: 100, Signed: 100, PowerSum: "1"},
		"c": {Expected: 100, Signed: 100, PowerSum: "1"},
	}
	payouts := calculateValidatorReservePayouts(budget, stats)
	total := new(big.Int)
	for _, amount := range payouts {
		total.Add(total, amount)
	}
	if total.Cmp(budget) > 0 {
		t.Fatalf("payout total %s exceeds budget %s", total, budget)
	}
	if total.String() != "9" {
		t.Fatalf("paid=%s, want 9 with one unit retained as rounding dust", total)
	}
}

func TestValidatorReserveMonthlyAnniversaryClampsEndOfMonth(t *testing.T) {
	start := time.Date(2026, time.January, 31, 12, 0, 0, 0, time.UTC)
	tests := []struct {
		at time.Time
		want int
	}{
		{start, 0},
		{time.Date(2026, time.February, 27, 12, 0, 0, 0, time.UTC), 0},
		{time.Date(2026, time.February, 28, 12, 0, 0, 0, time.UTC), 1},
		{time.Date(2026, time.March, 30, 12, 0, 0, 0, time.UTC), 1},
		{time.Date(2026, time.March, 31, 12, 0, 0, 0, time.UTC), 2},
	}
	for _, tt := range tests {
		if got := validatorReservePeriodIndex(start, tt.at); got != tt.want {
			t.Fatalf("period index for %s = %d, want %d", tt.at, got, tt.want)
		}
	}
}

func TestValidatorReserveScheduleMatchesLifetimeCap(t *testing.T) {
	totalScheduled := new(big.Int).Mul(new(big.Int).Set(validatorReserveMonthlyTranche), big.NewInt(validatorReservePeriods))
	if totalScheduled.Cmp(validatorReserveMaximum) != 0 {
		t.Fatalf("48 monthly tranches = %s, lifetime cap = %s", totalScheduled, validatorReserveMaximum)
	}
	want := new(big.Int).Mul(big.NewInt(150_000_000), new(big.Int).Exp(big.NewInt(10), big.NewInt(18), nil))
	if validatorReserveMaximum.Cmp(want) != 0 {
		t.Fatalf("lifetime cap = %s, want %s asobya", validatorReserveMaximum, want)
	}
}
