import os
import tempfile
import unittest
from pathlib import Path

from eth_keys import keys
from attestor_keystore import (
    KeystoreError, create_encrypted_keystore, load_encrypted_keystore,
    evm_signer_from_keystore,
)


class AttestorKeystoreTests(unittest.TestCase):
    def test_encrypted_keystore_round_trip_and_signer_address(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attestor.json"
            raw = bytes.fromhex("21" * 32)
            address = create_encrypted_keystore(path, raw, "a-long-test-passphrase-123")
            self.assertEqual(load_encrypted_keystore(path, "a-long-test-passphrase-123"), raw)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            signer = evm_signer_from_keystore(path, "a-long-test-passphrase-123")
            self.assertEqual(signer.address.lower(), address.lower())
            digest = bytes.fromhex("ab" * 32)
            signature = signer.sign(digest)
            self.assertEqual(len(signature), 65)

    def test_wrong_passphrase_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attestor.json"
            create_encrypted_keystore(path, bytes.fromhex("22" * 32), "a-long-test-passphrase-123")
            with self.assertRaises(KeystoreError):
                load_encrypted_keystore(path, "a-different-passphrase-456")

    def test_existing_keystore_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attestor.json"
            create_encrypted_keystore(path, bytes.fromhex("23" * 32), "a-long-test-passphrase-123")
            before = path.read_bytes()
            with self.assertRaises(KeystoreError):
                create_encrypted_keystore(path, bytes.fromhex("24" * 32), "a-long-test-passphrase-123")
            self.assertEqual(path.read_bytes(), before)

    def test_short_passphrase_and_invalid_key_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attestor.json"
            with self.assertRaises(KeystoreError):
                create_encrypted_keystore(path, bytes.fromhex("25" * 32), "short")
            with self.assertRaises(KeystoreError):
                create_encrypted_keystore(path, bytes(32), "a-long-test-passphrase-123")

    def test_keystore_rejects_group_or_world_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attestor.json"
            create_encrypted_keystore(path, bytes.fromhex("26" * 32), "a-long-test-passphrase-123")
            os.chmod(path, 0o644)
            with self.assertRaises(KeystoreError):
                load_encrypted_keystore(path, "a-long-test-passphrase-123")


if __name__ == "__main__":
    unittest.main(verbosity=2)
