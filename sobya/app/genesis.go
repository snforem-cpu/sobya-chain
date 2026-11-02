package app

import (
	"encoding/json"
	"fmt"

	sdkmath "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	minttypes "github.com/cosmos/cosmos-sdk/x/mint/types"
)

// GenesisState of the blockchain is represented here as a map of raw json
// messages key'd by a identifier string.
type GenesisState map[string]json.RawMessage

const (
	// BaseDenom is the smallest unit of the native SOBYA token.
	BaseDenom = "usobya"
	// DisplayDenom is the user-facing token denomination.
	DisplayDenom = "SOBY"
	// DisplayExponent defines 1 SOBY = 10^6 usobya.
	DisplayExponent uint32 = 6
	// MaxSupply is the hard maximum native supply in base units (1 billion SOBY).
	MaxSupply int64 = 1_000_000_000_000_000
)

// validateNativeSupply rejects genesis states that exceed the agreed SOBYA cap.
func validateNativeSupply(supply sdkmath.Int) error {
	if supply.IsNegative() {
		return fmt.Errorf("native SOBYA supply cannot be negative")
	}
	if supply.GT(sdkmath.NewInt(MaxSupply)) {
		return fmt.Errorf("native SOBYA supply %s exceeds maximum %d %s", supply, MaxSupply, BaseDenom)
	}
	return nil
}

func nativeDenomMetadata() banktypes.Metadata {
	return banktypes.Metadata{
		Description: "SOBYA native token; 1 SOBY = 1,000,000 usobya.",
		DenomUnits: []*banktypes.DenomUnit{
			{Denom: BaseDenom, Exponent: 0, Aliases: []string{"microSOBY"}},
			{Denom: DisplayDenom, Exponent: DisplayExponent},
		},
		Base:    BaseDenom,
		Display: DisplayDenom,
		Name:    "SOBYA",
		Symbol:  DisplayDenom,
	}
}

// prepareGenesisState canonicalizes native token metadata, disables inflation,
// and rejects a genesis allocation above the fixed maximum supply.
func prepareGenesisState(cdc codec.Codec, raw []byte) ([]byte, error) {
	appState := make(map[string]json.RawMessage)
	if err := json.Unmarshal(raw, &appState); err != nil {
		return nil, fmt.Errorf("decode application genesis: %w", err)
	}

	bankRaw, ok := appState[banktypes.ModuleName]
	if !ok {
		return nil, fmt.Errorf("application genesis is missing %q state", banktypes.ModuleName)
	}

	var bankGenesis banktypes.GenesisState
	if err := cdc.UnmarshalJSON(bankRaw, &bankGenesis); err != nil {
		return nil, fmt.Errorf("decode bank genesis: %w", err)
	}

	totalNative := sdkmath.ZeroInt()
	for _, balance := range bankGenesis.Balances {
		totalNative = totalNative.Add(balance.Coins.AmountOf(BaseDenom))
	}
	if err := validateNativeSupply(totalNative); err != nil {
		return nil, err
	}

	metadataFound := false
	for i, metadata := range bankGenesis.DenomMetadata {
		if metadata.Base == BaseDenom {
			bankGenesis.DenomMetadata[i] = nativeDenomMetadata()
			metadataFound = true
			break
		}
	}
	if !metadataFound {
		bankGenesis.DenomMetadata = append(bankGenesis.DenomMetadata, nativeDenomMetadata())
	}

	bankBytes, err := cdc.MarshalJSON(&bankGenesis)
	if err != nil {
		return nil, fmt.Errorf("encode normalized bank genesis: %w", err)
	}
	appState[banktypes.ModuleName] = bankBytes

	mintRaw, ok := appState[minttypes.ModuleName]
	if !ok {
		return nil, fmt.Errorf("application genesis is missing %q state", minttypes.ModuleName)
	}
	var mintGenesis minttypes.GenesisState
	if err := cdc.UnmarshalJSON(mintRaw, &mintGenesis); err != nil {
		return nil, fmt.Errorf("decode mint genesis: %w", err)
	}
	mintGenesis.Params.MintDenom = BaseDenom
	mintGenesis.Params.InflationRateChange = sdkmath.LegacyNewDec(0)
	mintGenesis.Params.InflationMax = sdkmath.LegacyNewDec(0)
	mintGenesis.Params.InflationMin = sdkmath.LegacyNewDec(0)
	mintGenesis.Minter.Inflation = sdkmath.LegacyNewDec(0)
	mintGenesis.Minter.AnnualProvisions = sdkmath.LegacyNewDec(0)

	mintBytes, err := cdc.MarshalJSON(&mintGenesis)
	if err != nil {
		return nil, fmt.Errorf("encode fixed-supply mint genesis: %w", err)
	}
	appState[minttypes.ModuleName] = mintBytes

	normalized, err := json.Marshal(appState)
	if err != nil {
		return nil, fmt.Errorf("encode normalized application genesis: %w", err)
	}
	return normalized, nil
}
