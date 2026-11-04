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
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
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

func TestValidatorReserveAccruedBudgetCarriesUnpaidTranches(t *testing.T) {
	tranche := new(big.Int).Set(validatorReserveMonthlyTranche)
	twoTranches := new(big.Int).Mul(new(big.Int).Set(tranche), big.NewInt(2))
	cases := []struct {
		name      string
		period    int
		totalPaid *big.Int
		want      *big.Int
	}{
		{name: "first period", period: 0, totalPaid: big.NewInt(0), want: tranche},
		{name: "one unpaid period rolls into second", period: 1, totalPaid: big.NewInt(0), want: twoTranches},
		{name: "fully paid first period leaves one tranche", period: 1, totalPaid: tranche, want: tranche},
		{name: "all 48 periods remain available", period: 47, totalPaid: big.NewInt(0), want: new(big.Int).Set(validatorReserveMaximum)},
		{name: "lifetime cap already paid", period: 47, totalPaid: new(big.Int).Set(validatorReserveMaximum), want: big.NewInt(0)},
		{name: "negative period", period: -1, totalPaid: big.NewInt(0), want: big.NewInt(0)},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := validatorReserveAccruedBudget(tc.period, tc.totalPaid)
			if got.Cmp(tc.want) != 0 {
				t.Fatalf("accrued budget = %s, want %s", got, tc.want)
			}
		})
	}
}

func TestValidatorReserveGenesisStoreRoundTrip(t *testing.T) {
	newContext := func() (*baseapp.BaseApp, sdk.Context, *storetypes.KVStoreKey) {
		db := dbm.NewMemDB()
		base := baseapp.NewBaseApp("validator-reserve-genesis-test", log.NewNopLogger(), db, func(tx []byte) (sdk.Tx, error) {
			return nil, nil
		})
		key := storetypes.NewKVStoreKey(validatorReserveStoreKeyName)
		base.MountKVStores(map[string]*storetypes.KVStoreKey{validatorReserveStoreKeyName: key})
		if err := base.LoadLatestVersion(); err != nil {
			t.Fatalf("load reserve test store: %v", err)
		}
		ctx := base.NewContextLegacy(true, cmtproto.Header{Height: 1})
		return base, ctx, key
	}

	baseA, ctxA, keyA := newContext()
	appA := &App{validatorReserveStoreKey: keyA}
	start := time.Date(2026, time.January, 31, 12, 0, 0, 0, time.UTC)
	meta := validatorReserveMeta{
		StartTime:     start.Format(time.RFC3339Nano),
		LastBlockTime: start.Add(24 * time.Hour).Format(time.RFC3339Nano),
		LastHeight:    77,
		TotalPaid:     "123456789",
	}
	storeA := ctxA.KVStore(keyA)
	if err := saveValidatorReserveMeta(storeA, meta); err != nil {
		t.Fatal(err)
	}
	operator := bytes.Repeat([]byte{0x11}, 20)
	consensus := bytes.Repeat([]byte{0x22}, 20)
	storeA.Set(validatorReserveConsensusKey(consensus), operator)
	statsKey := append(validatorReservePeriodStatsPrefix(0), operator...)
	if err := saveValidatorReserveStats(storeA, statsKey, validatorReserveStats{Expected: 100, Signed: 97, PowerSum: "987654321"}); err != nil {
		t.Fatal(err)
	}

	exported, err := appA.exportValidatorReserveGenesisState(ctxA)
	if err != nil {
		t.Fatalf("export reserve state: %v", err)
	}

	baseB, ctxB, keyB := newContext()
	appB := &App{validatorReserveStoreKey: keyB}
	if err := appB.initValidatorReserveGenesis(ctxB, exported); err != nil {
		t.Fatalf("restore reserve state: %v", err)
	}
	storeB := ctxB.KVStore(keyB)
	iterator := storeA.Iterator(nil, nil)
	defer iterator.Close()
	for ; iterator.Valid(); iterator.Next() {
		if got := storeB.Get(iterator.Key()); !bytes.Equal(got, iterator.Value()) {
			t.Fatalf("restored reserve value differs for key %X", iterator.Key())
		}
	}
	iteratorB := storeB.Iterator(nil, nil)
	defer iteratorB.Close()
	count := 0
	for ; iteratorB.Valid(); iteratorB.Next() {
		count++
	}
	if count != 3 {
		t.Fatalf("restored reserve key count=%d, want 3", count)
	}

	if err := appA.resetValidatorReserveHeightForZeroHeightExport(ctxA); err != nil {
		t.Fatalf("reset reserve height for zero-height export: %v", err)
	}
	resetMeta, err := appA.loadValidatorReserveMeta(storeA)
	if err != nil {
		t.Fatal(err)
	}
	if resetMeta.LastHeight != 0 {
		t.Fatalf("zero-height reserve last height=%d, want 0", resetMeta.LastHeight)
	}
	if resetMeta.LastBlockTime != meta.LastBlockTime {
		t.Fatalf("zero-height export changed accounting timestamp: got %s, want %s", resetMeta.LastBlockTime, meta.LastBlockTime)
	}

	_ = baseA
	_ = baseB
}

func TestValidatorReserveModuleAccountAddress(t *testing.T) {
	const expected = "sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr"
	if got := authtypes.NewModuleAddress(validatorReserveModuleName).String(); got != expected {
		t.Fatalf("validator reserve module account address=%s, want %s", got, expected)
	}
}
