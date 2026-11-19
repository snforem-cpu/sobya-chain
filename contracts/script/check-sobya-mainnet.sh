#!/usr/bin/env sh
# Read-only SOBYA Mainnet preflight. This script sends no transactions.
set -eu

RPC_URL="${SOBYA_RPC:-https://sobya-rpc.nodesafe-dapp.xyz}"
EXPECTED_CHAIN_ID="357812033857"

if ! command -v cast >/dev/null 2>&1; then
  echo "ERROR: Foundry cast is not installed." >&2
  exit 1
fi

echo "Checking SOBYA EVM RPC: $RPC_URL"
CHAIN_ID="$(cast chain-id --rpc-url "$RPC_URL")"
if [ "$CHAIN_ID" != "$EXPECTED_CHAIN_ID" ]; then
  echo "STOP: expected EVM chain ID $EXPECTED_CHAIN_ID, received $CHAIN_ID" >&2
  exit 2
fi

BLOCK_NUMBER="$(cast block-number --rpc-url "$RPC_URL")"
GAS_PRICE="$(cast gas-price --rpc-url "$RPC_URL")"

case "$BLOCK_NUMBER" in
  ''|*[!0-9]*) echo "STOP: invalid block number response: $BLOCK_NUMBER" >&2; exit 3 ;;
esac
case "$GAS_PRICE" in
  ''|*[!0-9]*) echo "STOP: invalid gas price response: $GAS_PRICE" >&2; exit 4 ;;
esac

echo "PASS: EVM chain ID = $CHAIN_ID"
echo "PASS: latest block = $BLOCK_NUMBER"
echo "PASS: RPC gas price response (wei) = $GAS_PRICE"
echo "READ-ONLY PREFLIGHT PASSED. No wallet was accessed and no transaction was sent."
