"""Interactive local CLI for creating and inspecting encrypted EVM attestor keys.

This tool generates keys locally, prompts for passphrases without echo, and
never prints or exports private key material.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys

from eth_keys import keys

from attestor_keystore import (
    KeystoreError, create_encrypted_keystore, load_encrypted_keystore,
)


def _new_private_key() -> bytes:
    for _ in range(128):
        candidate = secrets.token_bytes(32)
        try:
            return keys.PrivateKey(candidate).to_bytes()
        except Exception:
            continue
    raise RuntimeError("could not generate a valid secp256k1 key")


def create(path: str) -> str:
    first = getpass.getpass("New attestor keystore passphrase (16+ chars): ")
    second = getpass.getpass("Confirm passphrase: ")
    if first != second:
        raise KeystoreError("passphrases do not match")
    return create_encrypted_keystore(path, _new_private_key(), first)


def inspect(path: str) -> str:
    passphrase = getpass.getpass("Keystore passphrase: ")
    private_key = load_encrypted_keystore(path, passphrase)
    return keys.PrivateKey(private_key).public_key.to_checksum_address()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SOBYA local encrypted EVM attestor keystore")
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create", help="generate and encrypt a new local attestor key")
    create_parser.add_argument("--file", required=True, help="private keystore file path")
    inspect_parser = sub.add_parser("address", help="verify a keystore and print only its public address")
    inspect_parser.add_argument("--file", required=True, help="private keystore file path")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            address = create(args.file)
            print(f"Created encrypted keystore: {Path(args.file).expanduser()}")
            print(f"Attestor address: {address}")
            print("Private key material was not displayed. Back up this encrypted file offline.")
        else:
            print(f"Attestor address: {inspect(args.file)}")
        return 0
    except (KeystoreError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
