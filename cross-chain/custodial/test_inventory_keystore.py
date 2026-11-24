import os
import tempfile
import unittest
from pathlib import Path

from inventory_keystore import (
    InventoryKeystoreError, create_inventory_keystore, load_inventory_keystore,
)
from payout_executor import InventoryPayoutExecutor, PayoutError, PayoutJournal


class InventoryKeystoreTests(unittest.TestCase):
    def test_network_bound_encrypted_key_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "eth.key"
            raw = bytes.fromhex("11" * 32)
            create_inventory_keystore(str(path), "ethereum", raw, "correct horse battery staple")
            self.assertEqual(load_inventory_keystore(str(path), "ethereum", "correct horse battery staple"), raw)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_wrong_network_and_wrong_passphrase_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sol.key"
            raw = bytes.fromhex("22" * 64)
            create_inventory_keystore(str(path), "solana", raw, "correct horse battery staple")
            with self.assertRaises(InventoryKeystoreError):
                load_inventory_keystore(str(path), "tron", "correct horse battery staple")
            with self.assertRaises(InventoryKeystoreError):
                load_inventory_keystore(str(path), "solana", "wrong passphrase")

    def test_existing_keystore_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            create_inventory_keystore(str(path), "tron", bytes.fromhex("33" * 32), "correct horse battery staple")
            with self.assertRaises(InventoryKeystoreError):
                create_inventory_keystore(str(path), "tron", bytes.fromhex("44" * 32), "correct horse battery staple")


if __name__ == "__main__":
    unittest.main()
