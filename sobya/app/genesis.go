package app

import (
	"encoding/json"
	"fmt"

	sdkmath "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	minttypes "github.com/cosmos/cosmos-sdk/x/mint/types"
	distrtypes "github.com/cosmos/cosmos-sdk/x/distribution/types"
	evmtypes "github.com/cosmos/evm/x/vm/types"
)

// GenesisState of the blockchain is represented here as a map of raw json
// messages key'd by a identifier string.
type GenesisState map[string]json.RawMessage

const (
	// BaseDenom is the smallest unit of the native SOBYA token.
	BaseDenom = "asobya"
	// DisplayDenom is the user-facing token denomination.
	DisplayDenom = "SOBY"
	// DisplayExponent defines 1 SOBY = 10^18 asobya.
	DisplayExponent uint32 = 18
)

// MaxSupply is the hard maximum native supply in base units (1 billion SOBY).
var MaxSupply = sdkmath.NewIntWithDecimal(1_000_000_000, 18)


// validateNativeSupply rejects genesis states that exceed the agreed SOBYA cap.
func validateNativeSupply(supply sdkmath.Int) error {
	if supply.IsNegative() {
		return fmt.Errorf("native SOBYA supply cannot be negative")
	}
	if supply.GT(MaxSupply) {
		return fmt.Errorf("native SOBYA supply %s exceeds maximum %s %s", supply, MaxSupply.String(), BaseDenom)
	}
	return nil
}

func nativeDenomMetadata() banktypes.Metadata {
	return banktypes.Metadata{
		Description: "SOBYA native token; 1 SOBY = 1,000,000,000,000,000,000 asobya.",
		DenomUnits: []*banktypes.DenomUnit{
			{Denom: BaseDenom, Exponent: 0, Aliases: []string{"attoSOBY"}},
			{Denom: DisplayDenom, Exponent: DisplayExponent},
		},
		Base:    BaseDenom,
		Display: DisplayDenom,
		Name:    "SOBYA",
		Symbol:  DisplayDenom,
	}
}

// prepareGenesisState canonicalizes native token metadata, disables inflation,
// enables the supported Cosmos EVM static precompiles by default, and rejects
// a genesis allocation above the fixed maximum supply.
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

	// The fee router leaves exactly 30% in fee_collector for x/distribution.
	// Disable the SDK's default 2% community tax so validators receive that full
	// 30% when bonded voting power exists; otherwise the SDK routes it to its
	// community pool through its standard zero-power fallback.
	distrRaw, ok := appState[distrtypes.ModuleName]
	if !ok {
		return nil, fmt.Errorf("application genesis is missing %q state", distrtypes.ModuleName)
	}
	var distrGenesis distrtypes.GenesisState
	if err := cdc.UnmarshalJSON(distrRaw, &distrGenesis); err != nil {
		return nil, fmt.Errorf("decode distribution genesis: %w", err)
	}
	distrGenesis.Params.CommunityTax = sdkmath.LegacyZeroDec()
	distrBytes, err := cdc.MarshalJSON(&distrGenesis)
	if err != nil {
		return nil, fmt.Errorf("encode zero-tax distribution genesis: %w", err)
	}
	appState[distrtypes.ModuleName] = distrBytes

	// The EVM keeper registers the precompile implementations, but Cosmos EVM
	// executes only addresses enabled in evm.Params.ActiveStaticPrecompiles.
	// The upstream module default leaves this list empty, which silently disables
	// SOBYA's bank/staking/distribution/IBC/etc. precompiles on a fresh chain.
	// Enable the complete v0.6.0 set when the genesis has not selected any.
	if evmRaw, exists := appState[evmtypes.ModuleName]; exists {
		var evmGenesis evmtypes.GenesisState
		if err := cdc.UnmarshalJSON(evmRaw, &evmGenesis); err != nil {
			return nil, fmt.Errorf("decode EVM genesis: %w", err)
		}
		if len(evmGenesis.Params.ActiveStaticPrecompiles) == 0 {
			evmGenesis.Params.ActiveStaticPrecompiles = append(
				[]string(nil),
				evmtypes.AvailableStaticPrecompiles...,
			)
		}
		evmBytes, err := cdc.MarshalJSON(&evmGenesis)
		if err != nil {
			return nil, fmt.Errorf("encode EVM genesis with active static precompiles: %w", err)
		}
		appState[evmtypes.ModuleName] = evmBytes
	}

	normalized, err := json.Marshal(appState)
	if err != nil {
		return nil, fmt.Errorf("encode normalized application genesis: %w", err)
	}
	return normalized, nil
}
