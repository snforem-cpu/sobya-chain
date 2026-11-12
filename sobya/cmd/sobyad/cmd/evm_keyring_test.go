package cmd

import (
 "strings"
 "testing"

 "github.com/stretchr/testify/require"
 "github.com/cosmos/cosmos-sdk/codec"
 codectypes "github.com/cosmos/cosmos-sdk/codec/types"
 "github.com/cosmos/cosmos-sdk/crypto/keyring"
 "github.com/cosmos/cosmos-sdk/std"
 "github.com/cosmos/cosmos-sdk/types/tx/signing"
 evmhd "github.com/cosmos/evm/crypto/hd"
)

func TestEthSecp256k1FileKeyringRoundTrip(t *testing.T) {
 registry := codectypes.NewInterfaceRegistry()
 std.RegisterInterfaces(registry)
 registerEVMKeyringInterfaces(registry)
 cdc := codec.NewProtoCodec(registry)
 keyringDir := t.TempDir()
 kr, err := keyring.New("sobya", keyring.BackendFile, keyringDir, strings.NewReader("test-passphrase\ntest-passphrase\n"), cdc, evmhd.EthSecp256k1Option())
 require.NoError(t, err)
 _, _, err = kr.NewMnemonic("evm-account", keyring.English, "m/44'/60'/0'/0/0", "", evmhd.EthSecp256k1)
 require.NoError(t, err)
 reopened, err := keyring.New("sobya", keyring.BackendFile, keyringDir, strings.NewReader("test-passphrase\n"), cdc, evmhd.EthSecp256k1Option())
 require.NoError(t, err)
 message := []byte("SOBYA eth_secp256k1 file-keyring round trip")
 signature, pubKey, err := reopened.Sign("evm-account", message, signing.SignMode_SIGN_MODE_DIRECT)
 require.NoError(t, err)
 require.Equal(t, "eth_secp256k1", pubKey.Type())
 require.True(t, pubKey.VerifySignature(message, signature), "reopened EVM key must sign and verify")
}
