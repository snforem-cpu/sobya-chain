package app

import (
	"encoding/json"
	"testing"

	sdkmath "cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/gogoproto/proto"
	banktypes "github.com/cosmos/cosmos-sdk/x/bank/types"
	distrtypes "github.com/cosmos/cosmos-sdk/x/distribution/types"
	minttypes "github.com/cosmos/cosmos-sdk/x/mint/types"
	feemarkettypes "github.com/cosmos/evm/x/feemarket/types"
	evmtypes "github.com/cosmos/evm/x/vm/types"
)

func TestPrepareGenesisStateSetsApprovedEVMFeeMarket(t *testing.T) {
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
		feemarkettypes.ModuleName: marshal(feemarkettypes.DefaultGenesisState()),
		evmtypes.ModuleName:       marshal(evmtypes.DefaultGenesisState()),
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
	var got feemarkettypes.GenesisState
	if err := cdc.UnmarshalJSON(appState[feemarkettypes.ModuleName], &got); err != nil {
		t.Fatalf("unmarshal fee market genesis: %v", err)
	}
	if got.Params.NoBaseFee {
		t.Fatal("NoBaseFee must be false for production EIP-1559 fee charging")
	}
	if got.Params.EnableHeight != 0 {
		t.Fatalf("fee market enable height = %d, want 0", got.Params.EnableHeight)
	}
	want := sdkmath.LegacyNewDec(ApprovedEVMBaseFee)
	if !got.Params.BaseFee.Equal(want) {
		t.Fatalf("EVM base fee = %s, want %s", got.Params.BaseFee, want)
	}
}
