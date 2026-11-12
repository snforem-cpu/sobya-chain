package app

import (
	"encoding/json"
	"testing"

	sdkmath "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	"github.com/cosmos/gogoproto/proto"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	authtypes "github.com/cosmos/cosmos-sdk/x/auth/types"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	distrtypes "github.com/cosmos/cosmos-sdk/x/distribution/types"
	minttypes "github.com/cosmos/cosmos-sdk/x/mint/types"
	feemarkettypes "github.com/cosmos/evm/x/feemarket/types"
	evmtypes "github.com/cosmos/evm/x/vm/types"
)

func defaultFeeMarketGenesisRaw(t *testing.T, cdc codec.Codec) json.RawMessage {
	t.Helper()
	raw, err := cdc.MarshalJSON(feemarkettypes.DefaultGenesisState())
	if err != nil {
		t.Fatalf("marshal fee market genesis: %v", err)
	}
	return raw
}

func TestValidateNativeSupply(t *testing.T) {
	tests := []struct {
		name    string
		supply  sdkmath.Int
		wantErr bool
	}{
		{name: "zero supply", supply: sdkmath.NewInt(0)},
		{name: "below maximum", supply: MaxSupply.Sub(sdkmath.NewInt(1))},
		{name: "exact maximum", supply: MaxSupply},
		{name: "above maximum", supply: MaxSupply.Add(sdkmath.NewInt(1)), wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateNativeSupply(tt.supply)
			if (err != nil) != tt.wantErr {
				t.Fatalf("validateNativeSupply() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestNativeDenominationConstants(t *testing.T) {
	if sdk.DefaultBondDenom != BaseDenom {
		t.Fatalf("default bond denom = %s, want %s", sdk.DefaultBondDenom, BaseDenom)
	}
	if BaseDenom != "asobya" {
		t.Fatalf("unexpected base denom: %s", BaseDenom)
	}
	if DisplayDenom != "SOBY" {
		t.Fatalf("unexpected display denom: %s", DisplayDenom)
	}
	if DisplayExponent != 18 {
		t.Fatalf("unexpected display exponent: %d", DisplayExponent)
	}
	if !sdk.DefaultPowerReduction.Equal(sdkmath.NewIntWithDecimal(1, 18)) {
		t.Fatalf("default power reduction = %s, want 10^18", sdk.DefaultPowerReduction)
	}
	if !MaxSupply.Equal(sdkmath.NewIntWithDecimal(1_000_000_000, 18)) {
		t.Fatalf("unexpected maximum supply: %s", MaxSupply)
	}
}

func TestPrepareGenesisStateNormalizesTokenRules(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	bankGenesis := banktypes.DefaultGenesisState()
	mintGenesis := minttypes.DefaultGenesisState()
	distrGenesis := distrtypes.DefaultGenesisState()
	distrGenesis.Params.CommunityTax = sdkmath.LegacyNewDecWithPrec(2, 2)
	evmGenesis := evmtypes.DefaultGenesisState()

	bankBytes, err := cdc.MarshalJSON(bankGenesis)
	if err != nil {
		t.Fatalf("marshal bank genesis: %v", err)
	}
	mintBytes, err := cdc.MarshalJSON(mintGenesis)
	if err != nil {
		t.Fatalf("marshal mint genesis: %v", err)
	}
	distrBytes, err := cdc.MarshalJSON(distrGenesis)
	if err != nil {
		t.Fatalf("marshal distribution genesis: %v", err)
	}
	evmBytes, err := cdc.MarshalJSON(evmGenesis)
	if err != nil {
		t.Fatalf("marshal EVM genesis: %v", err)
	}
	raw, err := json.Marshal(map[string]json.RawMessage{
		banktypes.ModuleName:      bankBytes,
		minttypes.ModuleName:      mintBytes,
		distrtypes.ModuleName:     distrBytes,
		feemarkettypes.ModuleName: defaultFeeMarketGenesisRaw(t, cdc),
		evmtypes.ModuleName:       evmBytes,
	})
	if err != nil {
		t.Fatalf("marshal app genesis: %v", err)
	}

	normalized, err := prepareGenesisState(cdc, raw)
	if err != nil {
		t.Fatalf("prepareGenesisState() error: %v", err)
	}

	appState := make(map[string]json.RawMessage)
	if err := json.Unmarshal(normalized, &appState); err != nil {
		t.Fatalf("unmarshal normalized app genesis: %v", err)
	}

	var gotBank banktypes.GenesisState
	if err := cdc.UnmarshalJSON(appState[banktypes.ModuleName], &gotBank); err != nil {
		t.Fatalf("unmarshal normalized bank genesis: %v", err)
	}
	if len(gotBank.DenomMetadata) != 1 {
		t.Fatalf("expected one native denomination metadata entry, got %d", len(gotBank.DenomMetadata))
	}
	metadata := gotBank.DenomMetadata[0]
	if err := metadata.Validate(); err != nil {
		t.Fatalf("native denomination metadata is invalid: %v", err)
	}
	if metadata.Base != BaseDenom || metadata.Display != DisplayDenom {
		t.Fatalf("unexpected denomination metadata: base=%s display=%s", metadata.Base, metadata.Display)
	}

	var gotMint minttypes.GenesisState
	if err := cdc.UnmarshalJSON(appState[minttypes.ModuleName], &gotMint); err != nil {
		t.Fatalf("unmarshal normalized mint genesis: %v", err)
	}
	if gotMint.Params.MintDenom != BaseDenom {
		t.Fatalf("mint denom = %s, want %s", gotMint.Params.MintDenom, BaseDenom)
	}
	if !gotMint.Params.InflationRateChange.IsZero() || !gotMint.Params.InflationMax.IsZero() || !gotMint.Params.InflationMin.IsZero() {
		t.Fatal("mint inflation parameters were not all set to zero")
	}
	if !gotMint.Minter.Inflation.IsZero() || !gotMint.Minter.AnnualProvisions.IsZero() {
		t.Fatal("mint state still contains inflation or annual provisions")
	}

	var gotDistr distrtypes.GenesisState
	if err := cdc.UnmarshalJSON(appState[distrtypes.ModuleName], &gotDistr); err != nil {
		t.Fatalf("unmarshal normalized distribution genesis: %v", err)
	}
	if !gotDistr.Params.CommunityTax.IsZero() {
		t.Fatalf("distribution community tax = %s, want 0 for exact validator fee routing", gotDistr.Params.CommunityTax)
	}

	var gotEVM evmtypes.GenesisState
	if err := cdc.UnmarshalJSON(appState[evmtypes.ModuleName], &gotEVM); err != nil {
		t.Fatalf("unmarshal normalized EVM genesis: %v", err)
	}
	if gotEVM.Params.EvmDenom != BaseDenom {
		t.Fatalf("EVM gas denom = %s, want native SOBYA denom %s", gotEVM.Params.EvmDenom, BaseDenom)
	}
	if gotEVM.Params.ExtendedDenomOptions == nil || gotEVM.Params.ExtendedDenomOptions.ExtendedDenom != BaseDenom {
		t.Fatalf("EVM extended denom options = %v, want %s", gotEVM.Params.ExtendedDenomOptions, BaseDenom)
	}
	wantPrecompiles := []string{
		evmtypes.P256PrecompileAddress,
		evmtypes.Bech32PrecompileAddress,
		evmtypes.StakingPrecompileAddress,
		evmtypes.DistributionPrecompileAddress,
		evmtypes.ICS20PrecompileAddress,
		evmtypes.BankPrecompileAddress,
		evmtypes.GovPrecompileAddress,
		evmtypes.SlashingPrecompileAddress,
	}
	if len(gotEVM.Params.ActiveStaticPrecompiles) != len(wantPrecompiles) {
		t.Fatalf("active EVM precompile count = %d, want %d", len(gotEVM.Params.ActiveStaticPrecompiles), len(wantPrecompiles))
	}
	for i, want := range wantPrecompiles {
		if got := gotEVM.Params.ActiveStaticPrecompiles[i]; got != want {
			t.Fatalf("active EVM precompile[%d] = %s, want %s", i, got, want)
		}
	}
}

func TestPrepareGenesisStatePreservesValidatorReserveGenesisExtension(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	bankBytes, err := cdc.MarshalJSON(banktypes.DefaultGenesisState())
	if err != nil {
		t.Fatalf("marshal bank genesis: %v", err)
	}
	mintBytes, err := cdc.MarshalJSON(minttypes.DefaultGenesisState())
	if err != nil {
		t.Fatalf("marshal mint genesis: %v", err)
	}
	distrBytes, err := cdc.MarshalJSON(distrtypes.DefaultGenesisState())
	if err != nil {
		t.Fatalf("marshal distribution genesis: %v", err)
	}
	evmBytes, err := cdc.MarshalJSON(evmtypes.DefaultGenesisState())
	if err != nil {
		t.Fatalf("marshal EVM genesis: %v", err)
	}
	reserveExtension := json.RawMessage(`{"version":1,"entries":[{"key":"AA","value":"eyJzdGFydF90aW1lIjoiMjAyNy0wMS0wMVQwMDowMDowMFoiLCJsYXN0X2Jsb2NrX3RpbWUiOiIyMDI3LTAxLTAxVDAwOjAwOjAwWiIsImxhc3RfaGVpZ2h0IjowLCJ0b3RhbF9wYWlkX2Fzb2J5YSI6IjEwMDAwMDAwMDAwMDAwMDAwMDAwMDAifQ"}]}`)
	raw, err := json.Marshal(map[string]json.RawMessage{
		banktypes.ModuleName:      bankBytes,
		minttypes.ModuleName:      mintBytes,
		distrtypes.ModuleName:     distrBytes,
		feemarkettypes.ModuleName: defaultFeeMarketGenesisRaw(t, cdc),
		evmtypes.ModuleName:       evmBytes,
		validatorReserveGenesisKey: reserveExtension,
	})
	if err != nil {
		t.Fatalf("marshal application genesis: %v", err)
	}
	normalized, err := prepareGenesisState(cdc, raw)
	if err != nil {
		t.Fatalf("prepareGenesisState() error: %v", err)
	}
	appState := make(map[string]json.RawMessage)
	if err := json.Unmarshal(normalized, &appState); err != nil {
		t.Fatalf("unmarshal normalized application genesis: %v", err)
	}
	if string(appState[validatorReserveGenesisKey]) != string(reserveExtension) {
		t.Fatalf("validator reserve genesis extension changed: got %s, want %s", appState[validatorReserveGenesisKey], reserveExtension)
	}
}

func TestPrepareGenesisStateRejectsSupplyAboveCap(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	bankGenesis := banktypes.DefaultGenesisState()
	bankGenesis.Balances = []banktypes.Balance{{
		Address: "sobya1genesisallocationtest",
		Coins:   sdk.NewCoins(sdk.NewCoin(BaseDenom, MaxSupply.Add(sdkmath.NewInt(1)))),
	}}
	mintGenesis := minttypes.DefaultGenesisState()

	bankBytes, err := cdc.MarshalJSON(bankGenesis)
	if err != nil {
		t.Fatalf("marshal bank genesis: %v", err)
	}
	mintBytes, err := cdc.MarshalJSON(mintGenesis)
	if err != nil {
		t.Fatalf("marshal mint genesis: %v", err)
	}
	raw, err := json.Marshal(map[string]json.RawMessage{
		banktypes.ModuleName: bankBytes,
		minttypes.ModuleName: mintBytes,
	})
	if err != nil {
		t.Fatalf("marshal app genesis: %v", err)
	}

	if _, err := prepareGenesisState(cdc, raw); err == nil {
		t.Fatal("expected genesis above the native supply cap to be rejected")
	}
}

func TestMintModuleHasNoMintAuthority(t *testing.T) {
	for _, permission := range moduleAccPerms {
		if permission.Account != minttypes.ModuleName {
			continue
		}
		for _, capability := range permission.Permissions {
			if capability == authtypes.Minter {
				t.Fatal("mint module account must not retain the Minter permission")
			}
		}
		return
	}
	t.Fatal("mint module account permission entry is missing")
}

func TestNativeSupplyCapEndBlockInvariant(t *testing.T) {
	if err := validateNativeSupplyAtEndBlock(MaxSupply, 123); err != nil {
		t.Fatalf("exact native supply cap should pass at end of block: %v", err)
	}

	overCap := MaxSupply.Add(sdkmath.NewInt(1))
	if err := validateNativeSupplyAtEndBlock(overCap, 124); err == nil {
		t.Fatal("end-block native supply invariant must reject supply above the cap")
	}

	if err := validateNativeSupplyAtEndBlock(sdkmath.NewInt(-1), 125); err == nil {
		t.Fatal("end-block native supply invariant must reject a negative supply")
	}
}

func TestPrepareGenesisStatePreservesExplicitEVMPrecompileSelection(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	bankGenesis := banktypes.DefaultGenesisState()
	mintGenesis := minttypes.DefaultGenesisState()
	distrGenesis := distrtypes.DefaultGenesisState()
	evmGenesis := evmtypes.DefaultGenesisState()
	evmGenesis.Params.ActiveStaticPrecompiles = []string{evmtypes.Bech32PrecompileAddress}

	marshal := func(value proto.Message) json.RawMessage {
		t.Helper()
		raw, err := cdc.MarshalJSON(value)
		if err != nil {
			t.Fatalf("marshal genesis state: %v", err)
		}
		return raw
	}
	raw, err := json.Marshal(map[string]json.RawMessage{
		banktypes.ModuleName:      marshal(bankGenesis),
		minttypes.ModuleName:      marshal(mintGenesis),
		distrtypes.ModuleName:     marshal(distrGenesis),
		feemarkettypes.ModuleName: defaultFeeMarketGenesisRaw(t, cdc),
		evmtypes.ModuleName:       marshal(evmGenesis),
	})
	if err != nil {
		t.Fatalf("marshal application genesis: %v", err)
	}

	normalized, err := prepareGenesisState(cdc, raw)
	if err != nil {
		t.Fatalf("prepareGenesisState() error: %v", err)
	}
	appState := make(map[string]json.RawMessage)
	if err := json.Unmarshal(normalized, &appState); err != nil {
		t.Fatalf("unmarshal normalized application genesis: %v", err)
	}
	var got evmtypes.GenesisState
	if err := cdc.UnmarshalJSON(appState[evmtypes.ModuleName], &got); err != nil {
		t.Fatalf("unmarshal normalized EVM genesis: %v", err)
	}
	if len(got.Params.ActiveStaticPrecompiles) != 1 || got.Params.ActiveStaticPrecompiles[0] != evmtypes.Bech32PrecompileAddress {
		t.Fatalf("explicit EVM precompile selection changed: %v", got.Params.ActiveStaticPrecompiles)
	}
}

func TestPrepareGenesisStateRejectsMissingEVMGenesis(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	marshal := func(value proto.Message) json.RawMessage {
		t.Helper()
		raw, err := cdc.MarshalJSON(value)
		if err != nil {
			t.Fatalf("marshal genesis state: %v", err)
		}
		return raw
	}
	raw, err := json.Marshal(map[string]json.RawMessage{
		banktypes.ModuleName:      marshal(banktypes.DefaultGenesisState()),
		minttypes.ModuleName:      marshal(minttypes.DefaultGenesisState()),
		distrtypes.ModuleName:     marshal(distrtypes.DefaultGenesisState()),
		feemarkettypes.ModuleName: defaultFeeMarketGenesisRaw(t, cdc),
	})
	if err != nil {
		t.Fatalf("marshal application genesis: %v", err)
	}
	if _, err := prepareGenesisState(cdc, raw); err == nil {
		t.Fatal("expected genesis without EVM module state to be rejected")
	}
}
