"""Interactive local-only import for encrypted inventory signing keys."""
from __future__ import annotations
import argparse
import getpass
import json
import sys
from inventory_keystore import create_inventory_keystore, InventoryKeystoreError


def _read_key(network: str) -> bytes:
    entered = getpass.getpass("Private key (hidden; never paste it into chat or GitHub): ")
    try:
        if network == "solana":
            values = json.loads(entered)
            if not isinstance(values, list) or len(values) != 64 or any(
                not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 255 for v in values
            ):
                raise ValueError("Solana key must be a 64-byte JSON array")
            raw = bytes(values)
        else:
            raw = bytes.fromhex(entered.removeprefix("0x"))
            if len(raw) != 32:
                raise ValueError("EVM/TRON private key must be 32-byte hexadecimal")
        return raw
    finally:
        entered = ""


def _public_address(network: str, raw: bytes) -> str:
    if network in {"ethereum", "sobya"}:
        from eth_keys import keys
        return keys.PrivateKey(raw).public_key.to_checksum_address()
    if network == "tron":
        from tronpy.keys import PrivateKey
        return PrivateKey(raw).public_key.to_base58check_address()
    from solders.keypair import Keypair
    return str(Keypair.from_bytes(raw).pubkey())


def _addresses_match(network: str, derived: str, expected: str) -> bool:
    if not isinstance(expected, str) or not expected.strip():
        return False
    if network in {"ethereum", "sobya"}:
        return derived.lower() == expected.strip().lower()
    return derived == expected.strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create an encrypted local SOBYA inventory keystore")
    parser.add_argument("--network", choices=("ethereum","sobya","tron","solana"), required=True)
    parser.add_argument("--file", required=True, help="path outside the Git repository")
    parser.add_argument("--expected-address", required=True, help="configured public inventory address; key import aborts on mismatch")
    args = parser.parse_args(argv)
    try:
        raw = _read_key(args.network)
        address = _public_address(args.network, raw)
        if not _addresses_match(args.network, address, args.expected_address):
            raise InventoryKeystoreError("derived public address does not match configured inventory wallet; no keystore was written")
        first = getpass.getpass("New keystore passphrase (16+ characters): ")
        second = getpass.getpass("Confirm passphrase: ")
        if first != second:
            raise InventoryKeystoreError("passphrases do not match")
        create_inventory_keystore(args.file, args.network, raw, first)
        print(f"Encrypted {args.network} inventory keystore created.")
        print(f"Public address: {address}")
        print("Compare this address with the configured inventory wallet. Keep the encrypted file backed up offline.")
        return 0
    except Exception as exc:
        print(f"Keystore creation failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
