package app

import (
	"encoding/json"
	"fmt"

	sdkmath "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	minttypes "github.com/cosmos/cosmos-sdk/x/mint/types"
	distrtypes "github.com/cosmos/cosmos-sdk/x/distribution/types"
	feemarkettypes "github.com/cosmos/evm/x/feemarket/types"
	evmtypes "github.com/cosmos/evm/x/vm/types"
)

type GenesisState map[string]json.RawMessage

const (
	BaseDenom = "asobya"
	DisplayDenom = "SOBY"
	DisplayExponent uint32 = 18
	ApprovedEVMBaseFee int64 = 1_000_000_000
)

var MaxSupply = sdkmath.NewIntWithDecimal(1_000_000_000, 18)

func validateNativeSupply(supply sdkmath.Int) error {
	if supply.IsNegative() { return fmt.Errorf("native SOBYA supply cannot be negative") }
	if supply.GT(MaxSupply) { return fmt.Errorf("native SOBYA supply %s exceeds maximum %s %s", supply, MaxSupply.String(), BaseDenom) }
	return nil
}

func nativeDenomMetadata() banktypes.Metadata {
	return banktypes.Metadata{
		Description: "SOBYA native token; 1 SOBY = 1,000,000,000,000,000,000 asobya.",
		DenomUnits: []*banktypes.DenomUnit{
			{Denom: BaseDenom, Exponent: 0, Aliases: []string{"attoSOBY"}},
			{Denom: DisplayDenom, Exponent: DisplayExponent},
		},
		Base: BaseDenom, Display: DisplayDenom, Name: "SOBYA", Symbol: DisplayDenom,
	}
}

func defaultActiveEVMStaticPrecompiles() []string {
	return []string{
		evmtypes.P256PrecompileAddress, evmtypes.Bech32PrecompileAddress,
		evmtypes.StakingPrecompileAddress, evmtypes.DistributionPrecompileAddress,
		evmtypes.ICS20PrecompileAddress, evmtypes.BankPrecompileAddress,
		evmtypes.GovPrecompileAddress, evmtypes.SlashingPrecompileAddress,
	}
}

// prepareGenesisState applies SOBYA's fixed-supply, denomination and approved
// EVM fee defaults to a newly initialized genesis. It never rewrites live state.
func prepareGenesisState(cdc codec.Codec, raw []byte) ([]byte, error) {
	appState := make(map[string]json.RawMessage)
	if err := json.Unmarshal(raw, &appState); err != nil { return nil, fmt.Errorf("decode application genesis: %w", err) }

	bankRaw, ok := appState[banktypes.ModuleName]
	if !ok { return nil, fmt.Errorf("application genesis is missing %q state", banktypes.ModuleName) }
	var bankGenesis banktypes.GenesisState
	if err := cdc.UnmarshalJSON(bankRaw, &bankGenesis); err != nil { return nil, fmt.Errorf("decode bank genesis: %w", err) }
	totalNative := sdkmath.ZeroInt()
	for _, balance := range bankGenesis.Balances { totalNative = totalNative.Add(balance.Coins.AmountOf(BaseDenom)) }
	if err := validateNativeSupply(totalNative); err != nil { return nil, err }
	metadataFound := false
	for i, metadata := range bankGenesis.DenomMetadata {
		if metadata.Base == BaseDenom { bankGenesis.DenomMetadata[i] = nativeDenomMetadata(); metadataFound = true; break }
	}
	if !metadataFound { bankGenesis.DenomMetadata = append(bankGenesis.DenomMetadata, nativeDenomMetadata()) }
	bankBytes, err := cdc.MarshalJSON(&bankGenesis)
	if err != nil { return nil, fmt.Errorf("encode normalized bank genesis: %w", err) }
	appState[banktypes.ModuleName] = bankBytes

	mintRaw, ok := appState[minttypes.ModuleName]
	if !ok { return nil, fmt.Errorf("application genesis is missing %q state", minttypes.ModuleName) }
	var mintGenesis minttypes.GenesisState
	if err := cdc.UnmarshalJSON(mintRaw, &mintGenesis); err != nil { return nil, fmt.Errorf("decode mint genesis: %w", err) }
	mintGenesis.Params.MintDenom = BaseDenom
	mintGenesis.Params.InflationRateChange = sdkmath.LegacyNewDec(0)
	mintGenesis.Params.InflationMax = sdkmath.LegacyNewDec(0)
	mintGenesis.Params.InflationMin = sdkmath.LegacyNewDec(0)
	mintGenesis.Minter.Inflation = sdkmath.LegacyNewDec(0)
	mintGenesis.Minter.AnnualProvisions = sdkmath.LegacyNewDec(0)
	mintBytes, err := cdc.MarshalJSON(&mintGenesis)
	if err != nil { return nil, fmt.Errorf("encode fixed-supply mint genesis: %w", err) }
	appState[minttypes.ModuleName] = mintBytes

	distrRaw, ok := appState[distrtypes.ModuleName]
	if !ok { return nil, fmt.Errorf("application genesis is missing %q state", distrtypes.ModuleName) }
	var distrGenesis distrtypes.GenesisState
	if err := cdc.UnmarshalJSON(distrRaw, &distrGenesis); err != nil { return nil, fmt.Errorf("decode distribution genesis: %w", err) }
	distrGenesis.Params.CommunityTax = sdkmath.LegacyZeroDec()
	distrBytes, err := cdc.MarshalJSON(&distrGenesis)
	if err != nil { return nil, fmt.Errorf("encode zero-tax distribution genesis: %w", err) }
	appState[distrtypes.ModuleName] = distrBytes

	if feeMarketRaw, exists := appState[feemarkettypes.ModuleName]; exists {
		var feeMarketGenesis feemarkettypes.GenesisState
		if err := cdc.UnmarshalJSON(feeMarketRaw, &feeMarketGenesis); err != nil { return nil, fmt.Errorf("decode fee market genesis: %w", err) }
		feeMarketGenesis.Params.NoBaseFee = false
		feeMarketGenesis.Params.EnableHeight = 0
		feeMarketGenesis.Params.BaseFee = sdkmath.LegacyNewDec(ApprovedEVMBaseFee)
		feeMarketBytes, err := cdc.MarshalJSON(&feeMarketGenesis)
		if err != nil { return nil, fmt.Errorf("encode approved fee market genesis: %w", err) }
		appState[feemarkettypes.ModuleName] = feeMarketBytes
	}

	evmRaw, ok := appState[evmtypes.ModuleName]
	if !ok { return nil, fmt.Errorf("application genesis is missing %q state", evmtypes.ModuleName) }
	var evmGenesis evmtypes.GenesisState
	if err := cdc.UnmarshalJSON(evmRaw, &evmGenesis); err != nil { return nil, fmt.Errorf("decode EVM genesis: %w", err) }
	evmGenesis.Params.EvmDenom = BaseDenom
	if evmGenesis.Params.ExtendedDenomOptions == nil { evmGenesis.Params.ExtendedDenomOptions = &evmtypes.ExtendedDenomOptions{} }
	evmGenesis.Params.ExtendedDenomOptions.ExtendedDenom = BaseDenom
	if len(evmGenesis.Params.ActiveStaticPrecompiles) == 0 {
		evmGenesis.Params.ActiveStaticPrecompiles = append([]string(nil), defaultActiveEVMStaticPrecompiles()...)
	}
	evmBytes, err := cdc.MarshalJSON(&evmGenesis)
	if err != nil { return nil, fmt.Errorf("encode EVM genesis with active static precompiles: %w", err) }
	appState[evmtypes.ModuleName] = evmBytes

	normalized, err := json.Marshal(appState)
	if err != nil { return nil, fmt.Errorf("encode normalized application genesis: %w", err) }
	return normalized, nil
}
