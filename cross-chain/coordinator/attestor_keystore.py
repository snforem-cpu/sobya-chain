"""Encrypted local EVM attestor keystore.

Uses scrypt + XSalsa20-Poly1305 (PyNaCl SecretBox). Files are created
exclusively with mode 0600 and are never written into the repository by this
module. The operator must keep an offline backup of the encrypted file.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any

from nacl.secret import SecretBox
from nacl.exceptions import CryptoError
from eth_keys import keys


class KeystoreError(ValueError):
    pass


VERSION = 1
SCRYPT_N = 1 << 15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = SecretBox.KEY_SIZE


def _derive(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 16:
        raise KeystoreError("keystore passphrase must contain at least 16 characters")
    return hashlib.scrypt(
        passphrase.encode("utf-8"), salt=salt, n=SCRYPT_N,
        r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_LENGTH, maxmem=128 * 1024 * 1024,
    )


def _private_key(raw: bytes) -> keys.PrivateKey:
    if not isinstance(raw, bytes) or len(raw) != 32 or raw == bytes(32):
        raise KeystoreError("EVM private key must be exactly 32 non-zero bytes")
    try:
        return keys.PrivateKey(raw)
    except Exception as exc:
        raise KeystoreError("EVM private key is outside the secp256k1 scalar range") from exc


def create_encrypted_keystore(path: str | os.PathLike[str], private_key: bytes,
                              passphrase: str) -> str:
    """Create a new encrypted keystore without overwriting an existing path."""
    key = _private_key(private_key)
    target = Path(path).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    encryption_key = _derive(passphrase, salt)
    encrypted = SecretBox(encryption_key).encrypt(bytes(key), secrets.token_bytes(SecretBox.NONCE_SIZE))
    document = {
        "version": VERSION,
        "cipher": "xsalsa20-poly1305",
        "kdf": "scrypt",
        "scrypt": {"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P},
        "salt": base64.b64encode(salt).decode("ascii"),
        "ciphertext": base64.b64encode(bytes(encrypted)).decode("ascii"),
        "address": key.public_key.to_checksum_address(),
    }
    payload = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise KeystoreError("keystore already exists; refusing to overwrite") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    try:
        os.chmod(target, 0o600)
    except OSError:
        target.unlink(missing_ok=True)
        raise KeystoreError("could not enforce private keystore file permissions")
    return key.public_key.to_checksum_address()


def load_encrypted_keystore(path: str | os.PathLike[str], passphrase: str) -> bytes:
    """Decrypt and validate a local keystore; never logs or returns the passphrase."""
    target = Path(path).expanduser()
    try:
        info = target.lstat()
        if target.is_symlink() or not target.is_file() or info.st_mode & 0o077:
            raise KeystoreError("keystore must be a regular file with owner-only permissions")
        if info.st_size > 16_384:
            raise KeystoreError("keystore file exceeds the allowed size")
        document: Any = json.loads(target.read_text(encoding="utf-8"))
    except KeystoreError:
        raise
    except Exception as exc:
        raise KeystoreError("keystore file is unavailable or malformed") from exc
    expected = {"version", "cipher", "kdf", "scrypt", "salt", "ciphertext", "address"}
    if not isinstance(document, dict) or set(document) != expected:
        raise KeystoreError("keystore schema is invalid")
    if (document["version"] != VERSION or document["cipher"] != "xsalsa20-poly1305"
            or document["kdf"] != "scrypt"
            or document["scrypt"] != {"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P}):
        raise KeystoreError("unsupported keystore version or cryptographic parameters")
    try:
        salt = base64.b64decode(document["salt"], validate=True)
        ciphertext = base64.b64decode(document["ciphertext"], validate=True)
    except Exception as exc:
        raise KeystoreError("keystore encoding is invalid") from exc
    if len(salt) != 16 or len(ciphertext) != 32 + SecretBox.NONCE_SIZE + SecretBox.MACBYTES:
        raise KeystoreError("keystore salt or ciphertext has an invalid length")
    try:
        raw = SecretBox(_derive(passphrase, salt)).decrypt(ciphertext)
    except (CryptoError, ValueError) as exc:
        raise KeystoreError("keystore authentication failed (wrong passphrase or damaged file)") from exc
    key = _private_key(raw)
    if key.public_key.to_checksum_address().lower() != str(document["address"]).lower():
        raise KeystoreError("keystore public address does not match decrypted key")
    return bytes(key)


def evm_signer_from_keystore(path: str | os.PathLike[str], passphrase: str):
    """Return an EVM signing backend loaded from the encrypted local keystore."""
    from attestor_service import LocalEvmKeyBackend

    return LocalEvmKeyBackend(load_encrypted_keystore(path, passphrase))
