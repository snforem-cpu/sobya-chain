package app

import (
	"testing"

	sdkmath "cosmossdk.io/math"
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
