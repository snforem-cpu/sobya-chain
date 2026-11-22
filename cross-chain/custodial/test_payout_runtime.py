import tempfile
import unittest
from pathlib import Path

from custodial_ledger import CustodialOrderLedger
from payout_runtime import build_inventory_payout_executor


class PayoutRuntimeGateTests(unittest.TestCase):
    def test_example_disabled_networks_create_no_signing_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {
                "mode": "custodial-inventory",
                "featureEnabled": False,
                "networks": {
                    name: {"enabled": False}
                    for name in ("ethereum", "tron", "solana", "sobya")
                },
            }
            ledger = CustodialOrderLedger(Path(directory) / "orders.sqlite")
            executor = build_inventory_payout_executor(
                config, ledger, str(Path(directory) / "payout.sqlite")
            )
            self.assertFalse(executor.enabled)
            self.assertEqual(executor.adapters, {})

    def test_enabled_custody_allows_same_evm_address_on_ethereum_and_sobya(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {
                "mode": "custodial-inventory",
                "featureEnabled": True,
                "networks": {
                    "ethereum": {"enabled": False, "inventoryWallet": "0xebdb899fFE84a89e1d576964b640491c135651AD"},
                    "tron": {"enabled": False, "inventoryWallet": "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx"},
                    "solana": {"enabled": False, "inventoryWallet": "BMH7LJjaKkQRZd9EL4UqUfsTYEC44ZZoWSEdL1XWaSnh"},
                    "sobya": {"enabled": False, "inventoryWallet": "0xebdb899fFE84a89e1d576964b640491c135651AD"},
                },
            }
            ledger = CustodialOrderLedger(Path(directory) / "orders.sqlite")
            executor = build_inventory_payout_executor(
                config, ledger, str(Path(directory) / "payout.sqlite")
            )
            self.assertTrue(executor.enabled)
            self.assertEqual(executor.adapters, {})

    def test_enabled_custody_rejects_duplicate_non_evm_inventory_wallets(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {
                "mode": "custodial-inventory",
                "featureEnabled": True,
                "networks": {
                    "ethereum": {"enabled": False, "inventoryWallet": "0x1111111111111111111111111111111111111111"},
                    "tron": {"enabled": False, "inventoryWallet": "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx"},
                    "solana": {"enabled": False, "inventoryWallet": "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx"},
                    "sobya": {"enabled": False, "inventoryWallet": "0x2222222222222222222222222222222222222222"},
                },
            }
            ledger = CustodialOrderLedger(Path(directory) / "orders.sqlite")
            with self.assertRaisesRegex(ValueError, "duplicates"):
                build_inventory_payout_executor(
                    config, ledger, str(Path(directory) / "payout.sqlite")
                )

    def test_enabled_custody_requires_every_inventory_wallet(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {
                "mode": "custodial-inventory",
                "featureEnabled": True,
                "networks": {name: {"enabled": False, "inventoryWallet": "wallet-" + name}
                             for name in ("ethereum", "tron", "solana")},
            }
            ledger = CustodialOrderLedger(Path(directory) / "orders.sqlite")
            with self.assertRaisesRegex(ValueError, "sobya inventory wallet"):
                build_inventory_payout_executor(
                    config, ledger, str(Path(directory) / "payout.sqlite")
                )

    def test_wrong_mode_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build_inventory_payout_executor(
                    {"mode": "solver-escrow", "featureEnabled": False, "networks": {}},
                    object(), str(Path(directory) / "payout.sqlite"),
                )


if __name__ == "__main__":
    unittest.main()
