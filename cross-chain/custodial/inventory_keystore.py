"""Network-bound encrypted local inventory key files.

Uses scrypt and XSalsa20-Poly1305. The caller supplies raw key bytes in process;
the passphrase is read from an environment variable at runtime. Files are
created with owner-only permissions and are never written to the repository.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
from nacl.secret import SecretBox
from nacl.exceptions import CryptoError


class InventoryKeystoreError(ValueError):
    pass


def _derive(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 16:
        raise InventoryKeystoreError("keystore passphrase must be at least 16 characters")
    return hashlib.scrypt(passphrase.encode(), salt=salt, n=1 << 15, r=8, p=1,
                          dklen=SecretBox.KEY_SIZE, maxmem=128 * 1024 * 1024)


def create_inventory_keystore(path: str, network: str, raw_key: bytes, passphrase: str) -> None:
    if network not in {"ethereum","sobya","tron","solana"}:
        raise InventoryKeystoreError("unsupported inventory key network")
    allowed = {"ethereum": {32}, "sobya": {32}, "tron": {32}, "solana": {64}}
    if not isinstance(raw_key, bytes) or len(raw_key) not in allowed[network] or not any(raw_key):
        raise InventoryKeystoreError("private key has an invalid length or value for network")
    target = Path(path).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise InventoryKeystoreError("refusing to overwrite an existing keystore")
    salt = secrets.token_bytes(16)
    ciphertext = SecretBox(_derive(passphrase,salt)).encrypt(raw_key)
    doc = {"version":1,"network":network,"kdf":"scrypt","n":32768,"r":8,"p":1,
           "cipher":"xsalsa20-poly1305","salt":base64.b64encode(salt).decode(),
           "ciphertext":base64.b64encode(bytes(ciphertext)).decode()}
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"): flags |= os.O_NOFOLLOW
    fd = os.open(target,flags,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(doc,stream,sort_keys=True,separators=(",",":"))
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    os.chmod(target,0o600)


def load_inventory_keystore(path: str, network: str, passphrase: str) -> bytes:
    target=Path(path).expanduser()
    try:
        info=target.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size>16384:
            raise InventoryKeystoreError("keystore must be a small regular owner-only file")
        doc=json.loads(target.read_text(encoding="utf-8"))
    except InventoryKeystoreError: raise
    except Exception as exc: raise InventoryKeystoreError("keystore is unavailable or malformed") from exc
    expected={"version","network","kdf","n","r","p","cipher","salt","ciphertext"}
    if not isinstance(doc,dict) or set(doc)!=expected or doc["version"]!=1 or doc["network"]!=network:
        raise InventoryKeystoreError("keystore schema or network binding mismatch")
    if (doc["kdf"],doc["n"],doc["r"],doc["p"],doc["cipher"]) != ("scrypt",32768,8,1,"xsalsa20-poly1305"):
        raise InventoryKeystoreError("unsupported keystore cryptographic parameters")
    try:
        salt=base64.b64decode(doc["salt"],validate=True)
        ciphertext=base64.b64decode(doc["ciphertext"],validate=True)
        if len(salt)!=16: raise ValueError("salt")
        raw=SecretBox(_derive(passphrase,salt)).decrypt(ciphertext)
    except (ValueError,CryptoError) as exc:
        raise InventoryKeystoreError("keystore authentication failed") from exc
    allowed={"ethereum":32,"sobya":32,"tron":32,"solana":64}
    if network not in allowed or len(raw)!=allowed[network] or not any(raw):
        raise InventoryKeystoreError("decrypted key has invalid length for network")
    return raw


def load_inventory_keystore_from_env(path: str, network: str, passphrase_env: str) -> bytes:
    passphrase=os.environ.get(passphrase_env)
    if not passphrase:
        raise InventoryKeystoreError("local keystore passphrase environment variable is missing")
    return load_inventory_keystore(path,network,passphrase)
