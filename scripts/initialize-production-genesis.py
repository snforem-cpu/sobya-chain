#!/usr/bin/env python3
"""Build and validate SOBYA's fixed 1B-SOBY genesis allocation before validators join.

Run after `sobyad init` and after adding the founder and shared wallet balances
with the exact `sobyad genesis add-genesis-account` commands. The validator-reserve
module account is created by the app's module-account wiring; this script adds
its 150M bank balance without replacing the module account with a user account.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE_DENOM = "asobya"
FOUNDER_ADDRESS = "sobya16vtfjdprl33xsqu0fm375lqv2qu9z0qc0097pq"
SHARED_ADDRESS = "sobya1zhu55fp76czndk6342vn5e7n7t4q8as08t5yw3"
RESERVE_ADDRESS = "sobya1hmh9jk9gmk7k63qrpl3a9vsylcvrp379v3h0kr"
FOUNDER_AMOUNT = 400_000_000 * 10**18
SHARED_AMOUNT = 450_000_000 * 10**18
RESERVE_AMOUNT = 150_000_000 * 10**18
MAX_SUPPLY = 1_000_000_000 * 10**18
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


class GenesisError(Exception):
    pass


def fail(message: str) -> None:
    raise GenesisError(message)


def polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index, generator in enumerate(generators):
            if (top >> index) & 1:
                checksum ^= generator
    return checksum


def decode_sobya_address(address: str) -> bytes:
    if not isinstance(address, str) or address.lower() != address:
        fail(f"account address must be lowercase sobya Bech32: {address!r}")
    separator = address.rfind("1")
    if separator <= 0 or address[:separator] != "sobya":
        fail(f"account address must use the sobya prefix: {address!r}")
    encoded = address[separator + 1:]
    if len(encoded) < 6:
        fail(f"invalid Bech32 account address: {address!r}")
    try:
        data = [BECH32_CHARSET.index(char) for char in encoded]
    except ValueError:
        fail(f"invalid Bech32 character in account address: {address!r}")
    expanded = [ord(char) >> 5 for char in "sobya"] + [0] + [ord(char) & 31 for char in "sobya"]
    if polymod(expanded + data) != 1:
        fail(f"invalid Bech32 checksum: {address!r}")
    accumulator = 0
    bits = 0
    raw = bytearray()
    for value in data[:-6]:
        accumulator = (accumulator << 5) | value
        bits += 5
        if bits >= 8:
            bits -= 8
            raw.append((accumulator >> bits) & 255)
    if bits >= 5 or ((accumulator << (8 - bits)) & 255):
        fail(f"invalid Bech32 padding: {address!r}")
    if len(raw) != 20:
        fail(f"account address must decode to 20 bytes, got {len(raw)}: {address!r}")
    return bytes(raw)


def coin_map(coins: object, label: str) -> dict[str, int]:
    if not isinstance(coins, list):
        fail(f"{label} must be a coin list")
    result: dict[str, int] = {}
    for coin in coins:
        if not isinstance(coin, dict) or not isinstance(coin.get("denom"), str):
            fail(f"{label} contains an invalid coin")
        denom = coin["denom"]
        amount_text = str(coin.get("amount", ""))
        if denom in result or not re.fullmatch(r"[0-9]+", amount_text):
            fail(f"{label} contains duplicate denomination or invalid amount for {denom}")
        amount = int(amount_text)
        if amount < 0:
            fail(f"{label} contains negative amount for {denom}")
        if amount:
            result[denom] = amount
    return result


def coins_from_map(values: dict[str, int]) -> list[dict[str, str]]:
    return [{"denom": denom, "amount": str(values[denom])} for denom in sorted(values) if values[denom] > 0]


def collect_addresses(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, str):
            found.add(address)
        for child in value.values():
            found.update(collect_addresses(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_addresses(child))
    return found


def calculate_supply(balances: list[dict]) -> list[dict[str, str]]:
    totals: dict[str, int] = defaultdict(int)
    for balance in balances:
        for denom, amount in coin_map(balance.get("coins"), f"balance {balance.get('address')}").items():
            totals[denom] += amount
    return coins_from_map(dict(totals))


def prepare(genesis: dict) -> dict:
    if not isinstance(genesis, dict) or not genesis.get("chain_id"):
        fail("initialized genesis must contain a non-empty chain_id")
    app_state = genesis.get("app_state")
    if not isinstance(app_state, dict):
        fail("genesis app_state must be an object")
    if "sobya_validator_reserve" in app_state:
        fail("validator reserve extension already exists; use the validator self-bond reconciler only after operators join")
    auth = app_state.get("auth")
    bank = app_state.get("bank")
    if not isinstance(auth, dict) or not isinstance(bank, dict):
        fail("genesis must contain auth and bank module states")
    accounts = auth.get("accounts")
    balances = bank.get("balances")
    if not isinstance(accounts, list) or not isinstance(balances, list):
        fail("auth.accounts and bank.balances must be arrays")

    for address in (FOUNDER_ADDRESS, SHARED_ADDRESS, RESERVE_ADDRESS):
        decode_sobya_address(address)
    account_addresses = collect_addresses(accounts)
    for address, label in ((FOUNDER_ADDRESS, "founder"), (SHARED_ADDRESS, "shared management")):
        if address not in account_addresses:
            fail(f"{label} account {address} is missing from auth.accounts; run sobyad genesis add-genesis-account first")

    balance_by_address = {}
    for balance in balances:
        address = balance.get("address") if isinstance(balance, dict) else None
        if not isinstance(address, str) or address in balance_by_address:
            fail(f"missing or duplicate bank balance address: {address!r}")
        balance_by_address[address] = balance

    for address, expected, label in (
        (FOUNDER_ADDRESS, FOUNDER_AMOUNT, "founder"),
        (SHARED_ADDRESS, SHARED_AMOUNT, "shared management"),
    ):
        balance = balance_by_address.get(address)
        if balance is None:
            fail(f"{label} balance is missing; run sobyad genesis add-genesis-account for the exact allocation")
        actual = coin_map(balance.get("coins"), f"{label} balance").get(BASE_DENOM, 0)
        if actual != expected:
            fail(f"{label} balance is {actual} {BASE_DENOM}; expected exactly {expected}")

    if RESERVE_ADDRESS in balance_by_address:
        reserve = coin_map(balance_by_address[RESERVE_ADDRESS].get("coins"), "validator reserve balance")
        if reserve.get(BASE_DENOM, 0) != 0:
            fail("validator reserve bank balance is already funded; refusing to add the 150M allocation twice")
        reserve[BASE_DENOM] = RESERVE_AMOUNT
        balance_by_address[RESERVE_ADDRESS]["coins"] = coins_from_map(reserve)
    else:
        balances.append({"address": RESERVE_ADDRESS, "coins": [{"denom": BASE_DENOM, "amount": str(RESERVE_AMOUNT)}]})

    balances.sort(key=lambda item: item["address"])
    bank["supply"] = calculate_supply(balances)
    native_supply = next((int(coin["amount"]) for coin in bank["supply"] if coin["denom"] == BASE_DENOM), 0)
    if native_supply != MAX_SUPPLY:
        fail(f"native supply is {native_supply} {BASE_DENOM}; expected exactly {MAX_SUPPLY}")
    return genesis


def encode_for_test(payload: bytes) -> str:
    hrp = "sobya"
    accumulator = 0
    bits = 0
    data = []
    for value in payload:
        accumulator = (accumulator << 8) | value
        bits += 8
        while bits >= 5:
            bits -= 5
            data.append((accumulator >> bits) & 31)
    if bits:
        data.append((accumulator << (5 - bits)) & 31)
    expanded = [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]
    checksum_value = polymod(expanded + data + [0] * 6) ^ 1
    checksum = [(checksum_value >> (5 * (5 - i))) & 31 for i in range(6)]
    return hrp + "1" + "".join(BECH32_CHARSET[x] for x in data + checksum)


def self_test() -> None:
    validator = encode_for_test(bytes([0x44]) * 20)
    decode_sobya_address(validator)
    genesis = {
        "chain_id": "sobya-prelaunch-allocation-test",
        "app_state": {
            "auth": {"accounts": [
                {"@type": "/cosmos.auth.v1beta1.BaseAccount", "address": FOUNDER_ADDRESS},
                {"@type": "/cosmos.auth.v1beta1.BaseAccount", "address": SHARED_ADDRESS},
            ]},
            "bank": {
                "balances": [
                    {"address": FOUNDER_ADDRESS, "coins": [{"denom": BASE_DENOM, "amount": str(FOUNDER_AMOUNT)}]},
                    {"address": SHARED_ADDRESS, "coins": [{"denom": BASE_DENOM, "amount": str(SHARED_AMOUNT)}]},
                ],
                "supply": [{"denom": BASE_DENOM, "amount": str(FOUNDER_AMOUNT + SHARED_AMOUNT)}],
            },
        },
    }
    result = prepare(genesis)
    bank = result["app_state"]["bank"]
    reserve = next(item for item in bank["balances"] if item["address"] == RESERVE_ADDRESS)
    assert coin_map(reserve["coins"], "reserve")[BASE_DENOM] == RESERVE_AMOUNT
    assert next(int(item["amount"]) for item in bank["supply"] if item["denom"] == BASE_DENOM) == MAX_SUPPLY
    try:
        prepare(result)
    except GenesisError:
        pass
    else:
        fail("self-test did not reject adding the reserve allocation twice")
    print("PASS production allocation bootstrap: founder/shared balances, module account, 150M reserve, exact 1B native supply, duplicate protection")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genesis", type=Path, help="initialized genesis after founder/shared add-genesis-account commands")
    parser.add_argument("--output", type=Path, help="output path (defaults to overwriting --genesis)")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            return 0
        if not args.genesis:
            parser.error("--genesis is required unless --self-test is used")
        output = args.output or args.genesis
        genesis = json.loads(args.genesis.read_text(encoding="utf-8"))
        result = prepare(genesis)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("PASS: founder allocation = 400,000,000 SOBY")
        print("PASS: shared management allocations = 450,000,000 SOBY")
        print("PASS: validator reserve module account = 150,000,000 SOBY")
        print(f"PASS: native supply = exactly {MAX_SUPPLY} {BASE_DENOM}")
        print(f"Wrote {output}")
        return 0
    except (OSError, json.JSONDecodeError, GenesisError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
