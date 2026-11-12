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

	// ApprovedEVMBaseFee is the owner-approved EIP-1559 starting fee in asobya
	// per gas. It is deliberately separate from the validator-local minimum.
	ApprovedEVMBaseFee int64 = 1_000_000_000
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

// defaultActiveEVMStaticPrecompiles lists only the extension implementations
// actually registered by Cosmos EVM v0.6.0's DefaultStaticPrecompiles.
// The upstream AvailableStaticPrecompiles list also contains the legacy
// vesting address, for which v0.6.0 does not register an implementation.
func defaultActiveEVMStaticPrecompiles() []string {
	return []string{
		evmtypes.P256PrecompileAddress,
		evmtypes.Bech32PrecompileAddress,
		evmtypes.StakingPrecompileAddress,
		evmtypes.DistributionPrecompileAddress,
		evmtypes.ICS20PrecompileAddress,
		evmtypes.BankPrecompileAddress,
		evmtypes.GovPrecompileAddress,
		evmtypes.SlashingPrecompileAddress,
	}
}

// prepareGenesisState canonicalizes native token metadata, disables inflation,
// enables the supported Cosmos EVM static precompiles, applies the approved
// EIP-1559 starting base fee, and rejects allocations above the supply cap.
// This only affects a newly initialized genesis; it never rewrites live state.
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

	// Set the approved EIP-1559 base fee explicitly. The upstream default may
	// be overridden by an operator-provided genesis; leaving it at zero causes
	// eth_gasPrice and eth_feeHistory to quote zero and leaves MetaMask without
	// a usable fee estimate. MinGasPrice remains a separate governance/local
	// admission control; the approved starting base fee is the charge baseline.
	feeMarketRaw, ok := appState[feemarkettypes.ModuleName]
	if !ok {
		return nil, fmt.Errorf("application genesis is missing %q state", feemarkettypes.ModuleName)
	}
	var feeMarketGenesis feemarkettypes.GenesisState
	if err := cdc.UnmarshalJSON(feeMarketRaw, &feeMarketGenesis); err != nil {
		return nil, fmt.Errorf("decode fee market genesis: %w", err)
	}
	if feeMarketGenesis.Params == nil {
		return nil, fmt.Errorf("fee market genesis is missing params")
	}
	feeMarketGenesis.Params.NoBaseFee = false
	feeMarketGenesis.Params.EnableHeight = 0
	feeMarketGenesis.Params.BaseFee = sdkmath.LegacyNewDec(ApprovedEVMBaseFee)
	feeMarketBytes, err := cdc.MarshalJSON(&feeMarketGenesis)
	if err != nil {
		return nil, fmt.Errorf("encode approved fee market genesis: %w", err)
	}
	appState[feemarkettypes.ModuleName] = feeMarketBytes

	// The EVM keeper registers the precompile implementations, but Cosmos EVM
	// executes only addresses enabled in evm.Params.ActiveStaticPrecompiles.
	// A missing EVM genesis section must fail closed rather than silently launch
	// a chain where the registered Cosmos precompiles cannot execute.
	evmRaw, ok := appState[evmtypes.ModuleName]
	if !ok {
		return nil, fmt.Errorf("application genesis is missing %q state", evmtypes.ModuleName)
	}
	var evmGenesis evmtypes.GenesisState
	if err := cdc.UnmarshalJSON(evmRaw, &evmGenesis); err != nil {
		return nil, fmt.Errorf("decode EVM genesis: %w", err)
	}
	// Cosmos EVM defaults to the Cosmos Hub extended denom (aatom).
	// SOBYA's canonical 18-decimal bank coin is asobya, and EVM resolves
	// its gas coin metadata from Params.EvmDenom during InitGenesis.
	evmGenesis.Params.EvmDenom = BaseDenom
	if evmGenesis.Params.ExtendedDenomOptions == nil {
		evmGenesis.Params.ExtendedDenomOptions = &evmtypes.ExtendedDenomOptions{}
	}
	evmGenesis.Params.ExtendedDenomOptions.ExtendedDenom = BaseDenom

	if len(evmGenesis.Params.ActiveStaticPrecompiles) == 0 {
		evmGenesis.Params.ActiveStaticPrecompiles = append(
			[]string(nil),
			defaultActiveEVMStaticPrecompiles()...,
		)
	}
	evmBytes, err := cdc.MarshalJSON(&evmGenesis)
	if err != nil {
		return nil, fmt.Errorf("encode EVM genesis with active static precompiles: %w", err)
	}
	appState[evmtypes.ModuleName] = evmBytes

	normalized, err := json.Marshal(appState)
	if err != nil {
		return nil, fmt.Errorf("encode normalized application genesis: %w", err)
	}
	return normalized, nil
}
