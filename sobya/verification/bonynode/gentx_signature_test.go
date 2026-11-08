package bonynode

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	txsigning "cosmossdk.io/x/tx/signing"
	"github.com/cosmos/cosmos-sdk/codec"
	codectypes "github.com/cosmos/cosmos-sdk/codec/types"
	"github.com/cosmos/cosmos-sdk/std"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/x/auth/signing"
	authtx "github.com/cosmos/cosmos-sdk/x/auth/tx"
	stakingtypes "github.com/cosmos/cosmos-sdk/x/staking/types"
	"google.golang.org/protobuf/types/known/anypb"
)

const bonynode = "sobya19umw830rw5f5pwgfqk4yz976j5nl3h8h8j5a58"

func TestBonyNodeGentxCryptographicSignature(t *testing.T) {
	cfg := sdk.GetConfig()
	cfg.SetBech32PrefixForAccount("sobya", "sobyapub")
	cfg.SetBech32PrefixForValidator("sobyavaloper", "sobyavaloperpub")
	cfg.SetBech32PrefixForConsensusNode("sobyavalcons", "sobyavalconspub")
	cfg.Seal()

	repoRoot := filepath.Clean(filepath.Join("..", "..", ".."))
	gentxPath := filepath.Join(repoRoot, "verification", "bonynode", "SOBYA-gentx-BonyNode-2026-11-08-corrected.json")
	genesisPath := filepath.Join(repoRoot, ".github", "verification-placeholder")
	_ = genesisPath

	raw, err := os.ReadFile(gentxPath)
	if err != nil { t.Fatalf("read gentx: %v", err) }

	// Read account_number from the exact pre-gentx Genesis package extracted by the workflow.
	genesisPath = filepath.Join(os.Getenv("RUNNER_TEMP"), "pregen", "genesis.json")
	genesisRaw, err := os.ReadFile(genesisPath)
	if err != nil { t.Fatalf("read pre-gentx Genesis: %v", err) }
	var genesis struct {
		AppState struct {
			Auth struct {
				Accounts []struct {
					Address string `json:"address"`
					AccountNumber string `json:"account_number"`
				} `json:"accounts"`
			} `json:"auth"`
		} `json:"app_state"`
	}
	if err := json.Unmarshal(genesisRaw, &genesis); err != nil { t.Fatalf("decode Genesis: %v", err) }
	var accountNumber uint64
	found := false
	for _, a := range genesis.AppState.Auth.Accounts {
		if a.Address == bonynode {
			if _, err := fmt.Sscan(a.AccountNumber, &accountNumber); err != nil { t.Fatalf("parse account_number: %v", err) }
			found = true
			break
		}
	}
	if !found { t.Fatalf("BonyNode account %s absent from pre-gentx Genesis", bonynode) }

	registry := codectypes.NewInterfaceRegistry()
	std.RegisterInterfaces(registry)
	stakingtypes.RegisterInterfaces(registry)
	protoCodec := codec.NewProtoCodec(registry)
	txConfig := authtx.NewTxConfig(protoCodec, authtx.DefaultSignModes)

	decode := func(b []byte) sdk.Tx {
		tx, err := txConfig.TxJSONDecoder()(b)
		if err != nil { t.Fatalf("SDK TxJSONDecoder: %v", err) }
		return tx
	}
	tx := decode(raw)
	verify := func(tx sdk.Tx) error {
		sigTx, ok := tx.(signing.SigVerifiableTx)
		if !ok { t.Fatalf("decoded tx %T does not implement SigVerifiableTx", tx) }
		sigs, err := sigTx.GetSignaturesV2()
		if err != nil { t.Fatalf("GetSignaturesV2: %v", err) }
		signers, err := sigTx.GetSigners()
		if err != nil { t.Fatalf("GetSigners: %v", err) }
		if len(sigs) != 1 || len(signers) != 1 { t.Fatalf("expected one signer/signature; got %d/%d", len(signers), len(sigs)) }
		pubKey := sigs[0].PubKey
		if pubKey == nil { t.Fatal("signature public key is nil") }
		if !strings.EqualFold(sdk.AccAddress(pubKey.Address()).String(), bonynode) { t.Fatalf("pubkey address mismatch: %s", sdk.AccAddress(pubKey.Address())) }
		anyPK, err := codectypes.NewAnyWithValue(pubKey)
		if err != nil { t.Fatalf("pack public key: %v", err) }
		adaptable, ok := tx.(signing.V2AdaptableTx)
		if !ok { t.Fatalf("decoded tx %T does not implement V2AdaptableTx", tx) }
		signerData := txsigning.SignerData{
			Address: bonynode, ChainID: "sobya-1", AccountNumber: accountNumber, Sequence: sigs[0].Sequence,
			PubKey: &anypb.Any{TypeUrl: anyPK.TypeUrl, Value: anyPK.Value},
		}
		return signing.VerifySignature(context.Background(), pubKey, signerData, sigs[0].Data, txConfig.SignModeHandler(), adaptable.GetSigningTxData())
	}
	if err := verify(tx); err != nil { t.Fatalf("OFFICIAL COSMOS SDK SIGN_MODE_DIRECT verification FAILED: %v", err) }
	t.Logf("PASS: Cosmos SDK v0.53.6 verified BonyNode signature; chain_id=sobya-1 account_number=%d sequence=0", accountNumber)

	// Negative control: change a signed transaction field and require rejection.
	var altered map[string]any
	if err := json.Unmarshal(raw, &altered); err != nil { t.Fatal(err) }
	body := altered["body"].(map[string]any)
	body["memo"] = body["memo"].(string) + "-tampered"
	tampered, err := json.Marshal(altered)
	if err != nil { t.Fatal(err) }
	if err := verify(decode(tampered)); err == nil { t.Fatal("tamper test failed: altered transaction was accepted") }
	t.Log("PASS: tampered memo rejected by the same cryptographic verifier")
}
