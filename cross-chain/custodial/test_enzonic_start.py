import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import enzonic_start
from eth_account import Account
from inventory_keystore import create_inventory_keystore
from inventory_keystore_bootstrap import bootstrap_sobya_keystore


class EnzonicLauncherTests(unittest.TestCase):
    def test_bootstraps_only_a_disabled_local_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.example.json").write_text(json.dumps({
                "featureEnabled": False,
                "networks": {
                    name: {"enabled": False}
                    for name in ("ethereum", "tron", "solana", "sobya")
                },
            }), encoding="utf-8")
            template = json.loads((root / "config.example.json").read_text(encoding="utf-8"))
            template["networks"]["sobya"].update({
                "keystorePathEnv": "SOBYA_SOBYA_KEYSTORE",
                "keystorePassphraseEnv": "SOBYA_SOBYA_KEYSTORE_PASSPHRASE",
            })
            (root / "config.example.json").write_text(json.dumps(template), encoding="utf-8")
            old_cwd = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(
                os.environ, {}, clear=True
            ), patch("custodial_runtime.main", return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(), 0)
                    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
                    self.assertFalse(config["featureEnabled"])
                    self.assertTrue(all(
                        config["networks"][name]["enabled"] is False
                        for name in ("ethereum", "tron", "solana", "sobya")
                    ))
                    self.assertEqual(
                        os.environ["SOBYA_CUSTODIAL_CONFIG"], str(root / "config.json")
                    )
                    self.assertEqual(
                        Path(os.environ["SOBYA_CUSTODIAL_DB"]),
                        root / "data" / "orders.sqlite3",
                    )
                finally:
                    os.chdir(old_cwd)

    def test_existing_operator_config_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            disabled = {
                "featureEnabled": False,
                "networks": {
                    name: {"enabled": False}
                    for name in ("ethereum", "tron", "solana", "sobya")
                },
                "operatorConfig": True,
            }
            (root / "config.example.json").write_text("{}", encoding="utf-8")
            disabled["networks"]["sobya"].update({
                "keystorePathEnv": "SOBYA_SOBYA_KEYSTORE",
                "keystorePassphraseEnv": "SOBYA_SOBYA_KEYSTORE_PASSPHRASE",
            })
            config_path = root / "config.json"
            config_path.write_text(json.dumps(disabled), encoding="utf-8")
            old_cwd = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(
                os.environ, {"SOBYA_CUSTODIAL_CONFIG": str(config_path)}, clear=True
            ), patch("custodial_runtime.main", return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(), 0)
                    self.assertEqual(
                        json.loads(config_path.read_text(encoding="utf-8")),
                        disabled,
                    )
                finally:
                    os.chdir(old_cwd)

    def test_refuses_existing_config_with_any_live_gate_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.example.json").write_text("{}", encoding="utf-8")
            config_path = root / "config.json"
            config = {
                "featureEnabled": True,
                "networks": {
                    name: {"enabled": name == "ethereum"}
                    for name in ("ethereum", "tron", "solana", "sobya")
                },
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")
            old_cwd = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(
                os.environ, {"SOBYA_CUSTODIAL_CONFIG": str(config_path)}, clear=True
            ):
                try:
                    with self.assertRaisesRegex(SystemExit, "not authorized"):
                        enzonic_start.main()
                finally:
                    os.chdir(old_cwd)


    def test_existing_keystore_is_authenticated_and_address_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            checkout.mkdir()
            account = Account.create()
            key = bytes(account.key)
            keystore = root / "sobya-keystore.json"
            passphrase = "test-only-passphrase-123"
            create_inventory_keystore(str(keystore), "sobya", key, passphrase)
            original = keystore.read_bytes()
            config = {"networks": {"sobya": {
                "inventoryWallet": account.address,
                "keystorePathEnv": "SOBYA_SOBYA_KEYSTORE",
                "keystorePassphraseEnv": "SOBYA_SOBYA_KEYSTORE_PASSPHRASE",
            }}}
            with patch.dict(os.environ, {
                "SOBYA_SOBYA_KEYSTORE": str(keystore),
                "SOBYA_SOBYA_KEYSTORE_PASSPHRASE": passphrase,
            }, clear=True):
                self.assertEqual(bootstrap_sobya_keystore(config, checkout), "existing")
                self.assertEqual(keystore.read_bytes(), original)

    def test_existing_keystore_rejects_wrong_passphrase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            checkout.mkdir()
            account = Account.create()
            keystore = root / "sobya-keystore.json"
            create_inventory_keystore(str(keystore), "sobya", bytes(account.key), "correct-passphrase-123")
            config = {"networks": {"sobya": {
                "inventoryWallet": account.address,
                "keystorePathEnv": "SOBYA_SOBYA_KEYSTORE",
                "keystorePassphraseEnv": "SOBYA_SOBYA_KEYSTORE_PASSPHRASE",
            }}}
            with patch.dict(os.environ, {
                "SOBYA_SOBYA_KEYSTORE": str(keystore),
                "SOBYA_SOBYA_KEYSTORE_PASSPHRASE": "incorrect-passphrase-123",
            }, clear=True):
                with self.assertRaisesRegex(ValueError, "failed authentication"):
                    bootstrap_sobya_keystore(config, checkout)

    def test_existing_keystore_rejects_wallet_address_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            checkout.mkdir()
            account = Account.create()
            other = Account.create()
            keystore = root / "sobya-keystore.json"
            create_inventory_keystore(str(keystore), "sobya", bytes(account.key), "correct-passphrase-123")
            original = keystore.read_bytes()
            config = {"networks": {"sobya": {
                "inventoryWallet": other.address,
                "keystorePathEnv": "SOBYA_SOBYA_KEYSTORE",
                "keystorePassphraseEnv": "SOBYA_SOBYA_KEYSTORE_PASSPHRASE",
            }}}
            with patch.dict(os.environ, {
                "SOBYA_SOBYA_KEYSTORE": str(keystore),
                "SOBYA_SOBYA_KEYSTORE_PASSPHRASE": "correct-passphrase-123",
            }, clear=True):
                with self.assertRaisesRegex(ValueError, "failed authentication"):
                    bootstrap_sobya_keystore(config, checkout)
            self.assertEqual(keystore.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
