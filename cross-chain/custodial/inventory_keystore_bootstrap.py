"""One-time, address-checked SOBYA EVM keystore bootstrap for Enzonic.

The private key is read only from the Enzonic process environment when a new
keystore must be created. Existing keystores are authenticated and address-
checked on every startup. Secrets are never logged or written to the repository.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_KEYSTORE_PATH = Path("/home/container/secure/sobya-keystore.json")
PRIVATE_KEY_ENV = "SOBYA_SOBYA_PRIVATE_KEY"


def _normal_address(value: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise ValueError("configured inventory address is malformed")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise ValueError("configured inventory address is malformed") from exc
    if len(raw) != 20 or raw == bytes(20):
        raise ValueError("configured inventory address is malformed")
    return "0x" + raw.hex()


def bootstrap_sobya_keystore(config: dict[str, Any], repository_root: Path) -> str:
    networks = config.get("networks")
    sobya = networks.get("sobya") if isinstance(networks, dict) else None
    if not isinstance(sobya, dict):
        raise ValueError("SOBYA network configuration is missing")

    path_env = sobya.get("keystorePathEnv")
    passphrase_env = sobya.get("keystorePassphraseEnv")
    if not isinstance(path_env, str) or not path_env or not isinstance(passphrase_env, str) or not passphrase_env:
        raise ValueError("SOBYA keystore environment names are missing")

    target_value = os.environ.get(path_env)
    target = Path(target_value).expanduser() if target_value else DEFAULT_KEYSTORE_PATH
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
    root = repository_root.resolve()
    if target == root or root in target.parents:
        raise ValueError("SOBYA keystore must be stored outside the Git checkout")
    os.environ[path_env] = str(target)

    if target.exists() or target.is_symlink():
        # An existing file is never replaced. Authenticate it on every startup
        # and ensure it still controls the configured inventory wallet.
        from eth_account import Account
        from inventory_keystore import load_inventory_keystore

        passphrase = os.environ.get(passphrase_env)
        if not passphrase or len(passphrase) < 16:
            raise ValueError("existing SOBYA keystore cannot be verified: passphrase unavailable")
        try:
            recovered = load_inventory_keystore(str(target), "sobya", passphrase)
            recovered_address = _normal_address(Account.from_key(recovered).address)
            expected = _normal_address(sobya.get("inventoryWallet"))
            if recovered_address.lower() != expected.lower():
                raise ValueError("address mismatch")
        except Exception as exc:
            raise ValueError("existing SOBYA keystore failed authentication or wallet verification") from exc
        return "existing"

    key_text = os.environ.get(PRIVATE_KEY_ENV)
    if not key_text:
        return "not_configured"
    passphrase = os.environ.get(passphrase_env)
    if not passphrase or len(passphrase) < 16:
        raise ValueError("SOBYA keystore passphrase is missing or too short")

    # Never include the supplied key or passphrase in an exception or log.
    if key_text.startswith("0x"):
        key_text = key_text[2:]
    if len(key_text) != 64:
        raise ValueError("SOBYA private key must encode exactly 32 bytes")
    try:
        raw_key = bytes.fromhex(key_text)
    except ValueError as exc:
        raise ValueError("SOBYA private key is not valid hexadecimal") from exc
    if len(raw_key) != 32 or not any(raw_key):
        raise ValueError("SOBYA private key is invalid")

    from eth_account import Account
    from inventory_keystore import create_inventory_keystore, load_inventory_keystore

    expected = _normal_address(sobya.get("inventoryWallet"))
    actual = _normal_address(Account.from_key(raw_key).address)
    if actual.lower() != expected.lower():
        raise ValueError("SOBYA private key does not match the configured inventory wallet")

    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    try:
        create_inventory_keystore(str(target), "sobya", raw_key, passphrase)
        recovered = load_inventory_keystore(str(target), "sobya", passphrase)
        recovered_address = _normal_address(Account.from_key(recovered).address)
        if recovered_address.lower() != expected.lower():
            raise ValueError("created SOBYA keystore failed address verification")
        os.chmod(target, 0o600)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        os.environ.pop(PRIVATE_KEY_ENV, None)
        raw_key = b""
        key_text = ""

    return "created"
