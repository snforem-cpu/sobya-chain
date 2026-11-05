#!/usr/bin/env bash
# Probe SOBYA public P2P, CometBFT RPC, and EVM JSON-RPC from an external host.
set -euo pipefail

required=(SOBYA_P2P_HOST SOBYA_P2P_PORT SOBYA_RPC_URL SOBYA_EVM_RPC_URL SOBYA_CHAIN_ID SOBYA_EVM_CHAIN_ID)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "FAIL: missing required environment variable $name" >&2
    exit 2
  fi
done

for tool in curl jq nc; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "FAIL: required command not found: $tool" >&2
    exit 2
  }
done

[[ "$SOBYA_RPC_URL" == https://* ]] || { echo "FAIL: SOBYA_RPC_URL must use HTTPS" >&2; exit 2; }
[[ "$SOBYA_EVM_RPC_URL" == https://* ]] || { echo "FAIL: SOBYA_EVM_RPC_URL must use HTTPS" >&2; exit 2; }
[[ "$SOBYA_P2P_PORT" =~ ^[0-9]+$ ]] && (( SOBYA_P2P_PORT > 0 && SOBYA_P2P_PORT < 65536 )) || {
  echo "FAIL: invalid SOBYA_P2P_PORT" >&2
  exit 2
}

echo "Checking public P2P TCP reachability..."
nc -vz -w 8 "$SOBYA_P2P_HOST" "$SOBYA_P2P_PORT"

echo "Checking CometBFT RPC status..."
status="$(curl --fail --silent --show-error --max-time 10 "$SOBYA_RPC_URL/status")"
network="$(jq -r '.result.node_info.network // empty' <<<"$status")"
height="$(jq -r '.result.sync_info.latest_block_height // "0"' <<<"$status")"
[[ "$network" == "$SOBYA_CHAIN_ID" ]] || {
  echo "FAIL: CometBFT chain ID '$network' != expected '$SOBYA_CHAIN_ID'" >&2
  exit 1
}
[[ "$height" =~ ^[0-9]+$ ]] && (( height > 0 )) || {
  echo "FAIL: CometBFT has no committed blocks (height=$height)" >&2
  exit 1
}

echo "Checking connected CometBFT peers..."
net_info="$(curl --fail --silent --show-error --max-time 10 "$SOBYA_RPC_URL/net_info")"
peer_count="$(jq -r '.result.n_peers // "0"' <<<"$net_info")"
min_peers="${SOBYA_MIN_PEERS:-1}"
[[ "$peer_count" =~ ^[0-9]+$ ]] && (( peer_count >= min_peers )) || {
  echo "FAIL: connected peer count $peer_count is below required $min_peers" >&2
  exit 1
}

expected_evm_hex="$(printf '0x%x' "$SOBYA_EVM_CHAIN_ID")"
payload='{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
evm_response="$(curl --fail --silent --show-error --max-time 10 "$SOBYA_EVM_RPC_URL" -H 'content-type: application/json' --data "$payload")"
evm_chain_id="$(jq -r '.result // empty' <<<"$evm_response")"
[[ "${evm_chain_id,,}" == "${expected_evm_hex,,}" ]] || {
  echo "FAIL: EVM chain ID '$evm_chain_id' != expected '$expected_evm_hex'" >&2
  exit 1
}

payload='{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":2}'
evm_height_response="$(curl --fail --silent --show-error --max-time 10 "$SOBYA_EVM_RPC_URL" -H 'content-type: application/json' --data "$payload")"
evm_height="$(jq -r '.result // empty' <<<"$evm_height_response")"
[[ "$evm_height" =~ ^0x[0-9a-fA-F]+$ ]] || {
  echo "FAIL: invalid eth_blockNumber response '$evm_height'" >&2
  exit 1
}

echo "PASS: P2P TCP reachable at $SOBYA_P2P_HOST:$SOBYA_P2P_PORT"
echo "PASS: CometBFT chain=$network height=$height connected_peers=$peer_count"
echo "PASS: EVM chain=$evm_chain_id latest_block=$evm_height"
echo "NOTE: run this probe from outside the hosting network; a local success is not public reachability."
