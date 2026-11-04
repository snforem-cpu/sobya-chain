package app

import (
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math/big"
	"sort"
	"time"

	sdkmath "cosmossdk.io/math"
	storetypes "cosmossdk.io/store/types"
	abci "github.com/cometbft/cometbft/abci/types"
	cmtproto "github.com/cometbft/cometbft/proto/tendermint/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	distrtypes "github.com/cosmos/cosmos-sdk/x/distribution/types"
)

const (
	validatorReserveModuleName = "validator_reserve"
	validatorReserveStoreKeyName = "sobya_validator_reserve"
	validatorReservePeriods = 48
	validatorReserveEligibilityNumerator = 95
	validatorReserveEligibilityDenominator = 100
)

var (
	validatorReserveMonthlyTranche = new(big.Int).Mul(big.NewInt(3_125_000), new(big.Int).Exp(big.NewInt(10), big.NewInt(18), nil))
	validatorReserveMaximum = new(big.Int).Mul(big.NewInt(150_000_000), new(big.Int).Exp(big.NewInt(10), big.NewInt(18), nil))
	validatorReserveMetaKey = []byte{0x00}
	validatorReserveConsensusIndexPrefix = []byte{0x01}
	validatorReservePeriodPrefix = []byte{0x02}
)

type validatorReserveMeta struct {
	StartTime     string `json:"start_time"`
	LastBlockTime string `json:"last_block_time"`
	LastHeight    int64  `json:"last_height"`
	TotalPaid     string `json:"total_paid_asobya"`
}

type validatorReserveStats struct {
	Expected uint64 `json:"expected_blocks"`
	Signed   uint64 `json:"signed_blocks"`
	PowerSum string `json:"bonded_voting_power_sum"`
}


func validatorReservePeriodBoundary(start time.Time, index int) time.Time {
	start = start.UTC()
	month := time.Date(start.Year(), start.Month()+time.Month(index), 1, start.Hour(), start.Minute(), start.Second(), start.Nanosecond(), time.UTC)
	lastDay := time.Date(month.Year(), month.Month()+1, 0, 0, 0, 0, 0, time.UTC).Day()
	day := start.Day()
	if day > lastDay {
		day = lastDay
	}
	return time.Date(month.Year(), month.Month(), day, start.Hour(), start.Minute(), start.Second(), start.Nanosecond(), time.UTC)
}

// validatorReserveAccruedBudget returns the cumulative reserve allocation
// earned through a completed period, less amounts already paid. This carries
// forward every unpaid tranche instead of silently losing it at period close.
func validatorReserveAccruedBudget(period int, totalPaid *big.Int) *big.Int {
	if period < 0 {
		return new(big.Int)
	}
	if period >= validatorReservePeriods {
		period = validatorReservePeriods - 1
	}
	scheduled := new(big.Int).Mul(new(big.Int).Set(validatorReserveMonthlyTranche), big.NewInt(int64(period+1)))
	paid := new(big.Int)
	if totalPaid != nil && totalPaid.Sign() > 0 {
		paid.Set(totalPaid)
	}
	if paid.Cmp(scheduled) >= 0 {
		return new(big.Int)
	}
	return scheduled.Sub(scheduled, paid)
}

// validatorReservePeriodIndex uses monthly anniversaries in UTC. If the start
// day does not exist in a target month, that month's final day is used.
func validatorReservePeriodIndex(start, at time.Time) int {
	start, at = start.UTC(), at.UTC()
	if at.Before(start) {
		return -1
	}
	index := 0
	for index < validatorReservePeriods && !at.Before(validatorReservePeriodBoundary(start, index+1)) {
		index++
	}
	return index
}

func validatorReserveEligible(expected, signed uint64) bool {
	return expected > 0 && signed <= expected &&
		new(big.Int).Mul(new(big.Int).SetUint64(signed), big.NewInt(validatorReserveEligibilityDenominator)).Cmp(
			new(big.Int).Mul(new(big.Int).SetUint64(expected), big.NewInt(validatorReserveEligibilityNumerator)),
		) >= 0
}

// calculateValidatorReservePayouts weights shares by accumulated consensus
// voting power for all expected blocks. Ineligible shares and rounding dust
// are not redistributed; they remain in the reserve.
func calculateValidatorReservePayouts(budget *big.Int, stats map[string]validatorReserveStats) map[string]*big.Int {
	payouts := make(map[string]*big.Int)
	if budget == nil || budget.Sign() <= 0 {
		return payouts
	}
	totalPower := new(big.Int)
	powers := make(map[string]*big.Int, len(stats))
	for operator, stat := range stats {
		power, ok := new(big.Int).SetString(stat.PowerSum, 10)
		if !ok || power.Sign() <= 0 || stat.Expected == 0 {
			continue
		}
		powers[operator] = power
		totalPower.Add(totalPower, power)
	}
	if totalPower.Sign() == 0 {
		return payouts
	}
	for operator, stat := range stats {
		if !validatorReserveEligible(stat.Expected, stat.Signed) {
			continue
		}
		power := powers[operator]
		if power == nil || power.Sign() <= 0 {
			continue
		}
		amount := new(big.Int).Quo(new(big.Int).Mul(new(big.Int).Set(budget), power), totalPower)
		if amount.Sign() > 0 {
			payouts[operator] = amount
		}
	}
	return payouts
}

func validatorReservePeriodStatsPrefix(period int) []byte {
	key := make([]byte, 9)
	key[0] = validatorReservePeriodPrefix[0]
	binary.BigEndian.PutUint64(key[1:], uint64(period))
	return key
}

func validatorReserveConsensusKey(consAddr []byte) []byte {
	return append(append([]byte{}, validatorReserveConsensusIndexPrefix...), consAddr...)
}

func (app *App) loadValidatorReserveMeta(store storetypes.KVStore) (validatorReserveMeta, error) {
	raw := store.Get(validatorReserveMetaKey)
	if raw == nil {
		return validatorReserveMeta{}, nil
	}
	var meta validatorReserveMeta
	if err := json.Unmarshal(raw, &meta); err != nil {
		return meta, fmt.Errorf("decode validator reserve metadata: %w", err)
	}
	return meta, nil
}

func saveValidatorReserveMeta(store storetypes.KVStore, meta validatorReserveMeta) error {
	raw, err := json.Marshal(meta)
	if err != nil {
		return fmt.Errorf("encode validator reserve metadata: %w", err)
	}
	store.Set(validatorReserveMetaKey, raw)
	return nil
}

func loadValidatorReserveStats(store storetypes.KVStore, key []byte) (validatorReserveStats, error) {
	raw := store.Get(key)
	if raw == nil {
		return validatorReserveStats{PowerSum: "0"}, nil
	}
	var stats validatorReserveStats
	if err := json.Unmarshal(raw, &stats); err != nil {
		return stats, fmt.Errorf("decode validator reserve period statistics: %w", err)
	}
	if stats.PowerSum == "" {
		stats.PowerSum = "0"
	}
	return stats, nil
}

func saveValidatorReserveStats(store storetypes.KVStore, key []byte, stats validatorReserveStats) error {
	raw, err := json.Marshal(stats)
	if err != nil {
		return fmt.Errorf("encode validator reserve period statistics: %w", err)
	}
	store.Set(key, raw)
	return nil
}

// Refresh the consensus-key index after the previous commit has been
// recorded. This keeps the prior key available for one-block attribution
// across key rotation while preventing stale mappings from growing forever.
func (app *App) updateValidatorReserveConsensusIndex(ctx sdk.Context, store storetypes.KVStore) error {
	iterator := storetypes.KVStorePrefixIterator(store, validatorReserveConsensusIndexPrefix)
	keys := make([][]byte, 0)
	for ; iterator.Valid(); iterator.Next() {
		keys = append(keys, append([]byte{}, iterator.Key()...))
	}
	if err := iterator.Close(); err != nil {
		return fmt.Errorf("close validator reserve consensus-index iterator: %w", err)
	}
	for _, key := range keys {
		store.Delete(key)
	}

	validators, err := app.StakingKeeper.GetAllValidators(ctx)
	if err != nil {
		return fmt.Errorf("list validators for reserve accounting: %w", err)
	}
	for _, validator := range validators {
		if !validator.IsBonded() {
			continue
		}
		consAddr, err := validator.GetConsAddr()
		if err != nil {
			return fmt.Errorf("get consensus address for %s: %w", validator.GetOperator(), err)
		}
		operator, err := app.StakingKeeper.ValidatorAddressCodec().StringToBytes(validator.GetOperator())
		if err != nil {
			return fmt.Errorf("decode operator address %s: %w", validator.GetOperator(), err)
		}
		store.Set(validatorReserveConsensusKey(consAddr), operator)
	}
	return nil
}

func (app *App) recordValidatorReserveCommit(ctx sdk.Context, store storetypes.KVStore, period int, votes []abci.VoteInfo) error {
	if period < 0 || period >= validatorReservePeriods {
		return nil
	}
	for _, vote := range votes {
		if len(vote.Validator.Address) == 0 || vote.Validator.Power <= 0 {
			continue
		}
		consAddr := vote.Validator.Address
		operator := store.Get(validatorReserveConsensusKey(consAddr))
		if len(operator) == 0 {
			validator, err := app.StakingKeeper.GetValidatorByConsAddr(ctx, sdk.ConsAddress(consAddr))
			if err != nil {
				continue
			}
			operator, err = app.StakingKeeper.ValidatorAddressCodec().StringToBytes(validator.GetOperator())
			if err != nil {
				return fmt.Errorf("decode validator operator address: %w", err)
			}
			store.Set(validatorReserveConsensusKey(consAddr), operator)
		}
		key := append(validatorReservePeriodStatsPrefix(period), operator...)
		stats, err := loadValidatorReserveStats(store, key)
		if err != nil {
			return err
		}
		stats.Expected++
		if vote.BlockIdFlag == cmtproto.BlockIDFlagCommit {
			stats.Signed++
		}
		power, ok := new(big.Int).SetString(stats.PowerSum, 10)
		if !ok {
			return fmt.Errorf("invalid stored voting power sum for validator %X", operator)
		}
		power.Add(power, big.NewInt(vote.Validator.Power))
		stats.PowerSum = power.String()
		if err := saveValidatorReserveStats(store, key, stats); err != nil {
			return err
		}
	}
	return nil
}

func (app *App) validatorReserveBalance(ctx sdk.Context) *big.Int {
	address := authtypes.NewModuleAddress(validatorReserveModuleName)
	return app.BankKeeper.GetAllBalances(ctx, address).AmountOf(BaseDenom).BigInt()
}

// Each completed period can release at most one monthly tranche. Rewards are
// sent into x/distribution before BeginBlocker, then split by validator
// commission and delegator stake using the standard Cosmos distribution code.
func (app *App) closeValidatorReservePeriod(ctx sdk.Context, store storetypes.KVStore, period int, meta *validatorReserveMeta) error {
	prefix := validatorReservePeriodStatsPrefix(period)
	iterator := storetypes.KVStorePrefixIterator(store, prefix)
	statsByOperator := make(map[string]validatorReserveStats)
	keys := make([][]byte, 0)
	for ; iterator.Valid(); iterator.Next() {
		key := append([]byte{}, iterator.Key()...)
		var stats validatorReserveStats
		if err := json.Unmarshal(iterator.Value(), &stats); err != nil {
			_ = iterator.Close()
			return fmt.Errorf("decode reserve statistics for key %X: %w", key, err)
		}
		if stats.PowerSum == "" {
			stats.PowerSum = "0"
		}
		power, ok := new(big.Int).SetString(stats.PowerSum, 10)
		if !ok || power.Sign() <= 0 || stats.Expected == 0 || stats.Signed > stats.Expected {
			_ = iterator.Close()
			return fmt.Errorf("invalid validator reserve statistics for operator key %X", key[len(prefix):])
		}
		statsByOperator[string(key[len(prefix):])] = stats
		keys = append(keys, key)
	}
	if err := iterator.Close(); err != nil {
		return fmt.Errorf("close validator reserve iterator: %w", err)
	}

	totalPaid, ok := new(big.Int).SetString(meta.TotalPaid, 10)
	if !ok || totalPaid.Sign() < 0 || totalPaid.Cmp(validatorReserveMaximum) > 0 {
		return fmt.Errorf("invalid total-paid validator reserve value %q", meta.TotalPaid)
	}
	remainingCap := new(big.Int).Sub(new(big.Int).Set(validatorReserveMaximum), totalPaid)
	if remainingCap.Sign() < 0 {
		return fmt.Errorf("validator reserve lifetime cap exceeded: paid %s, cap %s", totalPaid, validatorReserveMaximum)
	}
	budget := validatorReserveAccruedBudget(period, totalPaid)
	if budget.Cmp(remainingCap) > 0 {
		budget.Set(remainingCap)
	}
	reserveBalance := app.validatorReserveBalance(ctx)
	if budget.Cmp(reserveBalance) > 0 {
		budget.Set(reserveBalance)
	}

	payouts := calculateValidatorReservePayouts(budget, statsByOperator)
	paidThisPeriod := new(big.Int)
	recipientCount := 0
	// Consensus-critical bank and distribution writes must use a stable order;
	// Go map iteration order is intentionally randomized.
	operators := make([]string, 0, len(payouts))
	for operator := range payouts {
		operators = append(operators, operator)
	}
	sort.Strings(operators)
	for _, operatorHex := range operators {
		amount := payouts[operatorHex]
		operator := []byte(operatorHex)
		validator, err := app.StakingKeeper.GetValidator(ctx, sdk.ValAddress(operator))
		if err != nil || !validator.IsBonded() || validator.Jailed {
			continue
		}
		coins := sdk.NewCoins(sdk.NewCoin(BaseDenom, sdkmath.NewIntFromBigInt(amount)))
		if err := app.BankKeeper.SendCoinsFromModuleToModule(ctx, validatorReserveModuleName, distrtypes.ModuleName, coins); err != nil {
			return fmt.Errorf("move validator reserve to distribution module for %s: %w", validator.GetOperator(), err)
		}
		if err := app.DistrKeeper.AllocateTokensToValidator(ctx, validator, sdk.NewDecCoinsFromCoins(coins...)); err != nil {
			return fmt.Errorf("allocate validator reserve rewards for %s: %w", validator.GetOperator(), err)
		}
		paidThisPeriod.Add(paidThisPeriod, amount)
		recipientCount++
	}

	totalPaid.Add(totalPaid, paidThisPeriod)
	meta.TotalPaid = totalPaid.String()
	for _, key := range keys {
		store.Delete(key)
	}
	ctx.EventManager().EmitEvent(sdk.NewEvent(
		"sobya_validator_reserve_release",
		sdk.NewAttribute("period", fmt.Sprintf("%d", period+1)),
		sdk.NewAttribute("amount_asobya", paidThisPeriod.String()),
		sdk.NewAttribute("eligible_recipients", fmt.Sprintf("%d", recipientCount)),
		sdk.NewAttribute("eligibility_threshold", "95/100"),
	))
	return nil
}

// installValidatorReserve validates the dedicated persistent store.
func (app *App) installValidatorReserve() error {
	if app.validatorReserveStoreKey == nil {
		return fmt.Errorf("validator reserve store key was not initialized")
	}
	return nil
}

// processValidatorReserve settles completed periods from actual CometBFT votes.
func (app *App) processValidatorReserve(ctx sdk.Context, req *abci.RequestFinalizeBlock) error {
	store := ctx.KVStore(app.validatorReserveStoreKey)
	meta, err := app.loadValidatorReserveMeta(store)
	if err != nil { return err }
	now := ctx.BlockTime().UTC()
	if meta.StartTime == "" {
		meta.StartTime = now.Format(time.RFC3339Nano)
		meta.LastBlockTime = now.Format(time.RFC3339Nano)
		meta.LastHeight = req.Height
		meta.TotalPaid = "0"
		if err := app.updateValidatorReserveConsensusIndex(ctx, store); err != nil { return err }
		return saveValidatorReserveMeta(store, meta)
	}
	if req.Height == meta.LastHeight { return nil }
	if req.Height != meta.LastHeight+1 {
		return fmt.Errorf("validator reserve expected height %d after %d, got %d", meta.LastHeight+1, meta.LastHeight, req.Height)
	}
	start, err := time.Parse(time.RFC3339Nano, meta.StartTime)
	if err != nil { return fmt.Errorf("parse validator reserve start time: %w", err) }
	lastTime, err := time.Parse(time.RFC3339Nano, meta.LastBlockTime)
	if err != nil { return fmt.Errorf("parse validator reserve previous block time: %w", err) }
	if now.Before(lastTime) { return fmt.Errorf("validator reserve block time moved backwards: %s before %s", now, lastTime) }
	previousPeriod := validatorReservePeriodIndex(start, lastTime)
	if err := app.recordValidatorReserveCommit(ctx, store, previousPeriod, req.DecidedLastCommit.Votes); err != nil { return err }
	currentPeriod := validatorReservePeriodIndex(start, now)
	for period := previousPeriod; period < currentPeriod && period < validatorReservePeriods; period++ {
		if period >= 0 {
			if err := app.closeValidatorReservePeriod(ctx, store, period, &meta); err != nil { return err }
		}
	}
	if err := app.updateValidatorReserveConsensusIndex(ctx, store); err != nil { return err }
	meta.LastBlockTime = now.Format(time.RFC3339Nano)
	meta.LastHeight = req.Height
	return saveValidatorReserveMeta(store, meta)
}

const validatorReserveGenesisKey = "sobya_validator_reserve"

type validatorReserveGenesisEntry struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

type validatorReserveGenesisState struct {
	Version uint32 `json:"version"`
	Entries []validatorReserveGenesisEntry `json:"entries"`
}

// exportValidatorReserveGenesisState makes the app-owned store participate in
// normal genesis export/import instead of silently losing accrued reserve data.
func (app *App) exportValidatorReserveGenesisState(ctx sdk.Context) ([]byte, error) {
	store := ctx.KVStore(app.validatorReserveStoreKey)
	iterator := store.Iterator(nil, nil)
	defer iterator.Close()

	state := validatorReserveGenesisState{Version: 1, Entries: make([]validatorReserveGenesisEntry, 0)}
	for ; iterator.Valid(); iterator.Next() {
		state.Entries = append(state.Entries, validatorReserveGenesisEntry{
			Key:   base64.RawStdEncoding.EncodeToString(iterator.Key()),
			Value: base64.RawStdEncoding.EncodeToString(iterator.Value()),
		})
	}
	return json.Marshal(state)
}

// initValidatorReserveGenesis validates and restores the app-owned reserve
// store from the explicit genesis extension emitted by ExportAppStateAndValidators.
func (app *App) initValidatorReserveGenesis(ctx sdk.Context, raw json.RawMessage) error {
	if len(raw) == 0 || string(raw) == "null" {
		return nil
	}
	var state validatorReserveGenesisState
	if err := json.Unmarshal(raw, &state); err != nil {
		return fmt.Errorf("decode validator reserve genesis state: %w", err)
	}
	if state.Version != 1 {
		return fmt.Errorf("unsupported validator reserve genesis version %d", state.Version)
	}

	store := ctx.KVStore(app.validatorReserveStoreKey)
	seen := make(map[string]struct{}, len(state.Entries))
	hasMeta := false
	for _, entry := range state.Entries {
		key, err := base64.RawStdEncoding.DecodeString(entry.Key)
		if err != nil {
			return fmt.Errorf("decode validator reserve genesis key: %w", err)
		}
		value, err := base64.RawStdEncoding.DecodeString(entry.Value)
		if err != nil {
			return fmt.Errorf("decode validator reserve genesis value: %w", err)
		}
		if _, exists := seen[string(key)]; exists {
			return fmt.Errorf("duplicate validator reserve genesis key %X", key)
		}
		seen[string(key)] = struct{}{}

		switch {
		case len(key) == 1 && key[0] == validatorReserveMetaKey[0]:
			var meta validatorReserveMeta
			if err := json.Unmarshal(value, &meta); err != nil {
				return fmt.Errorf("decode validator reserve genesis metadata: %w", err)
			}
			if _, err := time.Parse(time.RFC3339Nano, meta.StartTime); err != nil {
				return fmt.Errorf("invalid validator reserve genesis start time: %w", err)
			}
			if _, err := time.Parse(time.RFC3339Nano, meta.LastBlockTime); err != nil {
				return fmt.Errorf("invalid validator reserve genesis last block time: %w", err)
			}
			totalPaid, ok := new(big.Int).SetString(meta.TotalPaid, 10)
			if !ok || totalPaid.Sign() < 0 || totalPaid.Cmp(validatorReserveMaximum) > 0 || meta.LastHeight < 0 {
				return fmt.Errorf("invalid validator reserve genesis accounting metadata")
			}
			hasMeta = true
		case len(key) == 1+20 && key[0] == validatorReserveConsensusIndexPrefix[0]:
			// Consensus address -> validator operator address index.
			if len(value) != 20 {
				return fmt.Errorf("invalid validator operator address in reserve genesis index")
			}
		case len(key) == 1+8+20 && key[0] == validatorReservePeriodPrefix[0]:
			period := binary.BigEndian.Uint64(key[1:9])
			if period >= validatorReservePeriods {
				return fmt.Errorf("validator reserve genesis contains out-of-range period %d", period)
			}
			var stats validatorReserveStats
			if err := json.Unmarshal(value, &stats); err != nil {
				return fmt.Errorf("decode validator reserve genesis period stats: %w", err)
			}
			power, ok := new(big.Int).SetString(stats.PowerSum, 10)
			if !ok || power.Sign() <= 0 || stats.Expected == 0 || stats.Signed > stats.Expected {
				return fmt.Errorf("invalid validator reserve genesis period statistics")
			}
		default:
			return fmt.Errorf("unknown validator reserve genesis key %X", key)
		}
		store.Set(key, value)
	}
	if len(state.Entries) > 0 && !hasMeta {
		return fmt.Errorf("validator reserve genesis entries are missing metadata")
	}
	return nil
}

func (app *App) resetValidatorReserveHeightForZeroHeightExport(ctx sdk.Context) error {
	store := ctx.KVStore(app.validatorReserveStoreKey)
	meta, err := app.loadValidatorReserveMeta(store)
	if err != nil {
		return err
	}
	if meta.StartTime == "" {
		return nil
	}
	meta.LastHeight = 0
	return saveValidatorReserveMeta(store, meta)
}
