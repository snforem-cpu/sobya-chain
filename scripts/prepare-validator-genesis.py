#!/usr/bin/env python3
"""Reconcile validator genesis self-bonds against SOBYA's 150M reserve.

Run after `sobyad add-genesis-account` has created/funded each validator's
public account, but before gentx generation/collection. The script moves the
self-bond amounts from the validator reserve balance to those pre-funded
accounts without changing total native supply, and seeds the app-owned reserve
genesis extension so those initial self-bonds count against the 150M lifetime
validator budget.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DENOM = "asobya"
MAX_SUPPLY = 1_000_000_000 * 10**18
RESERVE_AMOUNT = 150_000_000 * 10**18
RESERVE_ADDRESS = "sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr"
FOUNDER_ADDRESS = "sobya16vtfjdprl33xsqu0fm375lqv2qu9z0qc0097pq"
SHARED_ADDRESS = "sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3"
RESERVE_GENESIS_KEY = "sobya_validator_reserve"
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


class GenesisError(Exception):
    pass


def fail(message: str) -> None:
    raise GenesisError(message)


def bech32_polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index, generator in enumerate(generators):
            if (top >> index) & 1:
                checksum ^= generator
    return checksum


def convertbits(data: list[int], from_bits: int, to_bits: int, pad: bool) -> bytes:
    accumulator = 0
    bits = 0
    result = bytearray()
    max_value = (1 << to_bits) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            fail("invalid Bech32 data value")
        accumulator = (accumulator << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((accumulator >> bits) & max_value)
    if pad:
        if bits:
            result.append((accumulator << (to_bits - bits)) & max_value)
    elif bits >= from_bits or ((accumulator << (to_bits - bits)) & max_value):
        fail("invalid Bech32 padding")
    return bytes(result)


def decode_sobya_address(address: str) -> bytes:
    if not isinstance(address, str) or address.lower() != address:
        fail(f"account address must be lowercase sobya Bech32: {address!r}")
    if address.count("1") < 1:
        fail(f"invalid Bech32 account address: {address!r}")
    separator = address.rfind("1")
    hrp, encoded = address[:separator], address[separator + 1:]
    if hrp != "sobya" or len(encoded) < 6:
        fail(f"account address must use the sobya prefix: {address!r}")
    try:
        data = [BECH32_CHARSET.index(char) for char in encoded]
    except ValueError:
        fail(f"invalid Bech32 character in account address: {address!r}")
    expanded = [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]
    if bech32_polymod(expanded + data) != 1:
        fail(f"invalid Bech32 checksum: {address!r}")
    raw = convertbits(data[:-6], 5, 8, False)
    if len(raw) != 20:
        fail(f"account address must decode to 20 bytes, got {len(raw)}: {address!r}")
    return raw


def parse_amount(value: object, label: str) -> int:
    if isinstance(value, bool):
        fail(f"{label} must be a positive integer string")
    text = str(value)
    if not re.fullmatch(r"[0-9]+", text):
        fail(f"{label} must be a positive integer string")
    amount = int(text)
    if amount <= 0:
        fail(f"{label} must be greater than zero")
    return amount


def utc_genesis_time(value: object) -> str:
    if not isinstance(value, str) or not value:
        fail("genesis_time is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"invalid genesis_time: {value!r}")
    if parsed.tzinfo is None:
        fail("genesis_time must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def coin_map(coins: object, label: str) -> dict[str, int]:
    if not isinstance(coins, list):
        fail(f"{label} must be a coin list")
    result: dict[str, int] = {}
    for coin in coins:
        if not isinstance(coin, dict) or not isinstance(coin.get("denom"), str):
            fail(f"{label} contains an invalid coin")
        denom = coin["denom"]
        if denom in result:
            fail(f"{label} contains duplicate denomination {denom}")
        amount_text = str(coin.get("amount", ""))
        if not re.fullmatch(r"[0-9]+", amount_text):
            fail(f"{label} has invalid amount for {denom}")
        amount = int(amount_text)
        if amount < 0:
            fail(f"{label} has negative amount for {denom}")
        if amount:
            result[denom] = amount
    return result


def coins_from_map(values: dict[str, int]) -> list[dict[str, str]]:
    return [{"denom": denom, "amount": str(values[denom])} for denom in sorted(values) if values[denom] > 0]


def recalculate_supply(balances: list[dict]) -> list[dict[str, str]]:
    totals: dict[str, int] = defaultdict(int)
    for balance in balances:
        for denom, amount in coin_map(balance.get("coins"), f"balance {balance.get('address')}").items():
            totals[denom] += amount
    return coins_from_map(dict(totals))


def prepare(genesis: dict, validators: list[dict]) -> dict:
    if not isinstance(genesis, dict) or not isinstance(genesis.get("app_state"), dict):
        fail("genesis must contain an app_state object")
    app_state = genesis["app_state"]
    bank = app_state.get("bank")
    auth = app_state.get("auth")
    if not isinstance(bank, dict) or not isinstance(auth, dict):
        fail("genesis app_state must contain bank and auth module states")
    if RESERVE_GENESIS_KEY in app_state:
        fail(f"{RESERVE_GENESIS_KEY} already exists; refusing to apply reserve reconciliation twice")

    genesis_time = utc_genesis_time(genesis.get("genesis_time"))
    balances = bank.get("balances")
    accounts = auth.get("accounts")
    if not isinstance(balances, list) or not isinstance(accounts, list):
        fail("bank.balances and auth.accounts must be arrays")

    balance_by_address: dict[str, dict] = {}
    for balance in balances:
        address = balance.get("address") if isinstance(balance, dict) else None
        if not isinstance(address, str) or address in balance_by_address:
            fail(f"missing or duplicate bank balance address: {address!r}")
        balance_by_address[address] = balance

    account_addresses = set()
    def collect_account_addresses(value: object) -> None:
        if isinstance(value, dict):
            address = value.get("address")
            if isinstance(address, str):
                account_addresses.add(address)
            for child in value.values():
                collect_account_addresses(child)
        elif isinstance(value, list):
            for child in value:
                collect_account_addresses(child)
    collect_account_addresses(accounts)

    expected_allocations = (
        (FOUNDER_ADDRESS, 400_000_000 * 10**18, "founder"),
        (SHARED_ADDRESS, 450_000_000 * 10**18, "shared management"),
        (RESERVE_ADDRESS, RESERVE_AMOUNT, "validator reserve module"),
    )
    for address, expected_amount, label in expected_allocations:
        if address not in account_addresses:
            fail(f"{label} account {address} is missing from auth.accounts")
        balance = balance_by_address.get(address)
        if balance is None:
            fail(f"{label} balance {address} is missing from bank.balances")
        amount = coin_map(balance.get("coins"), f"{label} balance").get(BASE_DENOM, 0)
        if amount != expected_amount:
            fail(f"{label} allocation is {amount} {BASE_DENOM}; expected exactly {expected_amount}")

    reserve_balance = balance_by_address[RESERVE_ADDRESS]
    reserve_coins = coin_map(reserve_balance.get("coins"), "validator reserve balance")

    if not validators:
        fail("at least one validator public account and self-bond allocation is required")
    seen = set()
    total_self_bond = 0
    parsed_validators = []
    forbidden = {RESERVE_ADDRESS, FOUNDER_ADDRESS, SHARED_ADDRESS}
    for index, item in enumerate(validators):
        if not isinstance(item, dict):
            fail(f"validator entry {index} must be an object")
        address = item.get("address")
        decode_sobya_address(address)
        if address in forbidden:
            fail(f"validator account cannot reuse a protocol allocation address: {address}")
        if address in seen:
            fail(f"duplicate validator account address: {address}")
        seen.add(address)
        amount = parse_amount(item.get("self_bond_asobya"), f"validator {address} self_bond_asobya")
        if address not in account_addresses:
            fail(f"validator {address} is absent from auth.accounts; run sobyad add-genesis-account first")
        balance = balance_by_address.get(address)
        if balance is None:
            fail(f"validator {address} is absent from bank.balances; run sobyad add-genesis-account first")
        coins = coin_map(balance.get("coins"), f"validator {address} balance")
        if coins.get(BASE_DENOM, 0) != amount:
            fail(f"validator {address} must have exactly {amount} {BASE_DENOM} from add-genesis-account before reconciliation")
        parsed_validators.append((address, amount))
        total_self_bond += amount

    if total_self_bond > RESERVE_AMOUNT:
        fail("validator self-bonds exceed the 150,000,000 SOBY lifetime validator allocation")

    reserve_coins[BASE_DENOM] -= total_self_bond
    reserve_balance["coins"] = coins_from_map(reserve_coins)

    total_supply = recalculate_supply(balances)
    native_supply = next((int(c["amount"]) for c in total_supply if c["denom"] == BASE_DENOM), 0)
    if native_supply != MAX_SUPPLY:
        fail(f"native supply after reconciliation is {native_supply}, expected exactly {MAX_SUPPLY} {BASE_DENOM}")
    bank["supply"] = total_supply

    metadata = {
        "start_time": genesis_time,
        "last_block_time": genesis_time,
        "last_height": 0,
        "total_paid_asobya": str(total_self_bond),
    }
    app_state[RESERVE_GENESIS_KEY] = {
        "version": 1,
        "entries": [{
            "key": base64.b64encode(b"\x00").decode("ascii").rstrip("="),
            "value": base64.b64encode(json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode()).decode("ascii").rstrip("="),
        }],
    }
    return genesis


def encode_bech32_for_test(payload: bytes) -> str:
    hrp = "sobya"
    acc = 0
    bits = 0
    data = []
    for value in payload:
        acc = (acc << 8) | value
        bits += 8
        while bits >= 5:
            bits -= 5
            data.append((acc >> bits) & 31)
    if bits:
        data.append((acc << (5 - bits)) & 31)
    expanded = [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]
    values = expanded + data + [0] * 6
    polymod = bech32_polymod(values) ^ 1
    checksum = [(polymod >> (5 * (5 - i))) & 31 for i in range(6)]
    return hrp + "1" + "".join(BECH32_CHARSET[x] for x in data + checksum)


def self_test() -> None:
    validator = encode_bech32_for_test(bytes([0x33]) * 20)
    decode_sobya_address(validator)
    accounts = [
        {"@type": "/cosmos.auth.v1beta1.BaseAccount", "address": FOUNDER_ADDRESS, "pub_key": None, "account_number": "0", "sequence": "0"},
        {"@type": "/cosmos.auth.v1beta1.BaseAccount", "address": SHARED_ADDRESS, "pub_key": None, "account_number": "1", "sequence": "0"},
        {"@type": "/cosmos.auth.v1beta1.ModuleAccount", "base_account": {"address": RESERVE_ADDRESS, "pub_key": None, "account_number": "2", "sequence": "0"}, "name": "validator_reserve", "permissions": []},
        {"@type": "/cosmos.auth.v1beta1.BaseAccount", "address": validator, "pub_key": None, "account_number": "3", "sequence": "0"},
    ]
    reserve_remaining = RESERVE_AMOUNT - 100 * 10**18
    initial_supply = MAX_SUPPLY + 100 * 10**18
    genesis = {
        "genesis_time": "2027-01-01T00:00:00Z",
        "chain_id": "sobya-prelaunch-selfbond-test",
        "app_state": {
            "auth": {"accounts": accounts, "params": {}},
            "bank": {
                "balances": [
                    {"address": FOUNDER_ADDRESS, "coins": [{"denom": BASE_DENOM, "amount": str(400_000_000 * 10**18)}]},
                    {"address": SHARED_ADDRESS, "coins": [{"denom": BASE_DENOM, "amount": str(450_000_000 * 10**18)}]},
                    {"address": RESERVE_ADDRESS, "coins": [{"denom": BASE_DENOM, "amount": str(RESERVE_AMOUNT)}]},
                    {"address": validator, "coins": [{"denom": BASE_DENOM, "amount": str(100 * 10**18)}]},
                ],
                "supply": [{"denom": BASE_DENOM, "amount": str(initial_supply)}],
            },
        },
    }
    result = prepare(genesis, [{"address": validator, "self_bond_asobya": str(100 * 10**18)}])
    bank = result["app_state"]["bank"]
    reserve = next(b for b in bank["balances"] if b["address"] == RESERVE_ADDRESS)
    validator_balance = next(b for b in bank["balances"] if b["address"] == validator)
    assert coin_map(reserve["coins"], "reserve")[BASE_DENOM] == reserve_remaining
    assert coin_map(validator_balance["coins"], "validator")[BASE_DENOM] == 100 * 10**18
    assert int(bank["supply"][0]["amount"]) == MAX_SUPPLY
    extension = result["app_state"][RESERVE_GENESIS_KEY]
    meta = json.loads(base64.b64decode(extension["entries"][0]["value"] + "=="))
    assert meta["total_paid_asobya"] == str(100 * 10**18)
    assert meta["last_height"] == 0
    try:
        prepare(result, [{"address": validator, "self_bond_asobya": str(100 * 10**18)}])
    except GenesisError:
        pass
    else:
        fail("self-test did not reject applying reconciliation twice")

    too_large = json.loads(json.dumps(genesis))
    try:
        prepare(too_large, [{"address": validator, "self_bond_asobya": str(RESERVE_AMOUNT + 1)}])
    except GenesisError:
        pass
    else:
        fail("self-test did not reject self-bonds above the reserve cap")
    print("PASS validator genesis self-bond reconciliation: account/bank balances, exact supply, reserve lifetime accounting, duplicate protection, and cap enforcement")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genesis", type=Path, help="genesis.json after add-genesis-account commands")
    parser.add_argument("--validators", type=Path, help="JSON array of validator account addresses and self_bond_asobya amounts")
    parser.add_argument("--output", type=Path, help="output path (defaults to overwriting --genesis)")
    parser.add_argument("--self-test", action="store_true", help="run deterministic fixture tests")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            return 0
        if not args.genesis or not args.validators:
            parser.error("--genesis and --validators are required unless --self-test is used")
        output = args.output or args.genesis
        genesis = json.loads(args.genesis.read_text(encoding="utf-8"))
        validators = json.loads(args.validators.read_text(encoding="utf-8"))
        result = prepare(genesis, validators)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"PASS: reconciled {len(validators)} validator self-bond(s)")
        print(f"PASS: validator self-bonds counted against the 150M lifetime reserve")
        print(f"PASS: native supply remains exactly {MAX_SUPPLY} {BASE_DENOM}")
        print(f"Wrote {output}")
        return 0
    except (OSError, json.JSONDecodeError, GenesisError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
