package app

import (
	"encoding/json"
	"testing"

	sdkmath "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	minttypes "github.com/cosmos/cosmos-sdk/x/mint/types"
)

func TestValidateNativeSupply(t *testing.T) {
	tests := []struct {
		name    string
		supply  int64
		wantErr bool
	}{
		{name: "zero supply", supply: 0},
		{name: "below maximum", supply: MaxSupply - 1},
		{name: "exact maximum", supply: MaxSupply},
		{name: "above maximum", supply: MaxSupply + 1, wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateNativeSupply(sdkmath.NewInt(tt.supply))
			if (err != nil) != tt.wantErr {
				t.Fatalf("validateNativeSupply() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestNativeDenominationConstants(t *testing.T) {
	if BaseDenom != "usobya" {
		t.Fatalf("unexpected base denom: %s", BaseDenom)
	}
	if DisplayDenom != "SOBY" {
		t.Fatalf("unexpected display denom: %s", DisplayDenom)
	}
	if DisplayExponent != 6 {
		t.Fatalf("unexpected display exponent: %d", DisplayExponent)
	}
	if MaxSupply != 1_000_000_000_000_000 {
		t.Fatalf("unexpected maximum supply: %d", MaxSupply)
	}
}

func TestPrepareGenesisStateNormalizesTokenRules(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	bankGenesis := banktypes.DefaultGenesisState()
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
}

func TestPrepareGenesisStateRejectsSupplyAboveCap(t *testing.T) {
	cdc := codec.NewProtoCodec(codectypes.NewInterfaceRegistry())
	bankGenesis := banktypes.DefaultGenesisState()
	bankGenesis.Balances = []banktypes.Balance{{
		Address: "sobya1genesisallocationtest",
		Coins:   sdk.NewCoins(sdk.NewCoin(BaseDenom, sdkmath.NewInt(MaxSupply+1))),
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
