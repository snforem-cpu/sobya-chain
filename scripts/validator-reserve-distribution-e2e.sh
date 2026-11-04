#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/sobyad"
NET="${NET:-$RUNNER_TEMP/sobya-validator-reserve-e2e}"
CHAIN_ID="sobya-reserve-e2e-1"
RPC0="http://127.0.0.1:26657"
RPC1="http://127.0.0.1:26654"
mkdir -p "$NET"

cd "$ROOT/sobya"
go build -mod=readonly -o "$BIN" ./cmd/sobyad

"$BIN" multi-node \
  --v 2 \
  --output-dir "$NET" \
  --chain-id "$CHAIN_ID" \
  --validators-stake-amount 100000000000000000000,100000000000000000000 \
  --list-ports 26657,26654 \
  --starting-ip-address 127.0.0.1 \
  --keyring-backend test \
  --minimum-gas-prices 0asobya

# Seed a matured reserve period in genesis so the real PreBlocker -> bank ->
# x/distribution path can be exercised immediately, without waiting 30 days.
python3 - "$NET/validator0/config/genesis.json" "$NET/validator1/config/genesis.json" <<'PY'
import base64, datetime, json, pathlib, struct, sys

source = pathlib.Path(sys.argv[1])
genesis = json.loads(source.read_text(encoding="utf-8"))
app = genesis["app_state"]
bank = app["bank"]
staking = app["staking"]
reserve_address = "sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr"
reserve_amount = 150_000_000 * 10**18

def b64raw(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii").rstrip("=")

def bech32_decode(value: str) -> bytes:
    alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    hrp, data = value.rsplit("1", 1)
    values = [alphabet.index(c) for c in data[:-6]]
    acc = bits = 0
    out = []
    for v in values:
        acc = (acc << 5) | v
        bits += 5
        while bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 255)
    if bits >= 5 or ((acc << (8-bits)) & 255):
        raise ValueError("invalid bech32 padding")
    return bytes(out)

validators = staking.get("validators", [])
if len(validators) < 2:
    raise SystemExit(f"expected two genesis validators, found {len(validators)}")

operator_bytes = []
for validator in validators[:2]:
    operator_bytes.append(bech32_decode(validator["operator_address"]))
    commission = validator.setdefault("commission", {})
    rates = commission.setdefault("commission_rates", {})
    rates["rate"] = "0.100000000000000000"
    rates["max_rate"] = "1.000000000000000000"
    rates["max_change_rate"] = "0.100000000000000000"

# Fund the dedicated reserve module account and recompute bank supply exactly.
balances = bank.setdefault("balances", [])
existing = next((b for b in balances if b["address"] == reserve_address), None)
if existing is None:
    balances.append({"address": reserve_address, "coins": [{"denom": "asobya", "amount": str(reserve_amount)}]})
else:
    coins = existing.setdefault("coins", [])
    coin = next((c for c in coins if c["denom"] == "asobya"), None)
    if coin is None:
        coins.append({"denom": "asobya", "amount": str(reserve_amount)})
    else:
        coin["amount"] = str(int(coin["amount"]) + reserve_amount)

for balance in balances:
    balance["coins"] = sorted(balance.get("coins", []), key=lambda c: c["denom"])
balances.sort(key=lambda b: b["address"])
supply = {}
for balance in balances:
    for coin in balance.get("coins", []):
        supply[coin["denom"]] = supply.get(coin["denom"], 0) + int(coin["amount"])
bank["supply"] = [{"denom": d, "amount": str(supply[d])} for d in sorted(supply)]

genesis_time = datetime.datetime.fromisoformat(genesis["genesis_time"].replace("Z", "+00:00"))
start = genesis_time - datetime.timedelta(days=90)
last = start + datetime.timedelta(days=30)
def stamp(value):
    return value.isoformat(timespec="nanoseconds").replace("+00:00", "Z")

entries = [
    {"key": b64raw(b"\x00"), "value": b64raw(json.dumps({
        "start_time": stamp(start),
        "last_block_time": stamp(last),
        "last_height": 0,
        "total_paid_asobya": "0"
    }, separators=(",", ":")).encode())}
]
for operator in operator_bytes:
    key = b"\x02" + struct.pack(">Q", 1) + operator
    value = json.dumps({
        "expected_blocks": 100,
        "signed_blocks": 100,
        "bonded_voting_power_sum": "100000"
    }, separators=(",", ":")).encode()
    entries.append({"key": b64raw(key), "value": b64raw(value)})

app["sobya_validator_reserve"] = {"version": 1, "entries": entries}
encoded = json.dumps(genesis, indent=2) + "\n"
source.write_text(encoded, encoding="utf-8")
pathlib.Path(sys.argv[2]).write_text(encoded, encoding="utf-8")
print("Seeded 150,000,000 SOBY reserve and a matured, fully eligible two-validator period.")
PY

cmp "$NET/validator0/config/genesis.json" "$NET/validator1/config/genesis.json"
test "$(jq -r '.chain_id' "$NET/validator0/config/genesis.json")" = "$CHAIN_ID"

"$BIN" start --chain-id "$CHAIN_ID" --home "$NET/validator0" > "$NET/validator0.log" 2>&1 &
PID0=$!
"$BIN" start --chain-id "$CHAIN_ID" --home "$NET/validator1" > "$NET/validator1.log" 2>&1 &
PID1=$!
cleanup() {
  for pid in "$PID0" "$PID1"; do kill "$pid" 2>/dev/null || true; done
  for pid in "$PID0" "$PID1"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT

rpc_ready() {
  local url="$1"
  for _ in $(seq 1 90); do
    if curl --connect-timeout 2 --max-time 5 -fsS "$url/status" | jq -e '.result.sync_info.latest_block_height' >/dev/null; then return 0; fi
    sleep 2
  done
  return 1
}
rpc_ready "$RPC0" || { cat "$NET/validator0.log"; exit 1; }
rpc_ready "$RPC1" || { cat "$NET/validator1.log"; exit 1; }

HEIGHT=0
for _ in $(seq 1 90); do
  HEIGHT="$(curl -fsS "$RPC0/status" | jq -r '.result.sync_info.latest_block_height')"
  if [ "$HEIGHT" -ge 2 ]; then break; fi
  sleep 2
done
test "$HEIGHT" -ge 2

KEYS0="$NET/keys0.json"
KEYS1="$NET/keys1.json"
"$BIN" keys list --keyring-backend test --home "$NET/validator0" --output json > "$KEYS0"
"$BIN" keys list --keyring-backend test --home "$NET/validator1" --output json > "$KEYS1"
KEY0="$(jq -r '.[0].name' "$KEYS0")"
ADDR0="$(jq -r '.[0].address' "$KEYS0")"
VAL0="$("$BIN" keys show "$KEY0" --bech val --keyring-backend test --home "$NET/validator0" -a)"
KEY1="$(jq -r '.[0].name' "$KEYS1")"
ADDR1="$(jq -r '.[0].address' "$KEYS1")"
VAL1="$("$BIN" keys show "$KEY1" --bech val --keyring-backend test --home "$NET/validator1" -a)"

query_positive_asobya() {
  local file="$1"
  jq -e '[.. | objects | select(.denom? == "asobya") | (.amount | tonumber)] | add // 0 | . > 0' "$file" >/dev/null
}
for val in "$VAL0" "$VAL1"; do
  "$BIN" query distribution commission "$val" --node "$RPC0" --home "$NET/validator0" --output json > "$NET/commission-$val.json"
  query_positive_asobya "$NET/commission-$val.json"
done
"$BIN" query distribution rewards "$ADDR0" "$VAL0" --node "$RPC0" --home "$NET/validator0" --output json > "$NET/delegator-rewards-0.json"
"$BIN" query distribution rewards "$ADDR1" "$VAL1" --node "$RPC0" --home "$NET/validator1" --output json > "$NET/delegator-rewards-1.json"
query_positive_asobya "$NET/delegator-rewards-0.json"
query_positive_asobya "$NET/delegator-rewards-1.json"
echo "PASS: reserve payout created real validator commission and self-delegator rewards for both validators."

# Withdraw both commission and delegator rewards through signed transactions.
for idx in 0 1; do
  if [ "$idx" -eq 0 ]; then KEY="$KEY0"; VAL="$VAL0"; HOME="$NET/validator0"; NODE="$RPC0"; else KEY="$KEY1"; VAL="$VAL1"; HOME="$NET/validator1"; NODE="$RPC1"; fi
  "$BIN" tx distribution withdraw-rewards "$VAL" --commission --from "$KEY" --chain-id "$CHAIN_ID" --node "$NODE" --home "$HOME" --keyring-backend test --fees 1000000000000000asobya --gas 300000 --broadcast-mode sync --yes --output json > "$NET/commission-withdraw-$idx.json"
  test "$(jq -r '.code // .tx_response.code // 0' "$NET/commission-withdraw-$idx.json")" = "0"
  "$BIN" tx distribution withdraw-rewards "$VAL" --from "$KEY" --chain-id "$CHAIN_ID" --node "$NODE" --home "$HOME" --keyring-backend test --fees 1000000000000000asobya --gas 300000 --broadcast-mode sync --yes --output json > "$NET/delegator-withdraw-$idx.json"
  test "$(jq -r '.code // .tx_response.code // 0' "$NET/delegator-withdraw-$idx.json")" = "0"
done

# Verify the matured period was settled exactly once: block 1 has one release
# event; the following block has none.
for height in 1 2; do
  curl --connect-timeout 2 --max-time 5 -fsS "$RPC0/block_results?height=$height" > "$NET/block-results-$height.json"
done
EVENTS1="$(jq '[.result.finalize_block_events[]? | select(.type == "sobya_validator_reserve_release")] | length' "$NET/block-results-1.json")"
EVENTS2="$(jq '[.result.finalize_block_events[]? | select(.type == "sobya_validator_reserve_release")] | length' "$NET/block-results-2.json")"
test "$EVENTS1" -eq 1
test "$EVENTS2" -eq 0
echo "PASS: reserve release occurred once, and no duplicate release occurred in the next block."

echo "PASS: end-to-end validator reserve -> distribution -> commission/delegator withdrawals."
