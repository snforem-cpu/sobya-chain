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

    def test_wrong_mode_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build_inventory_payout_executor(
                    {"mode": "solver-escrow", "featureEnabled": False, "networks": {}},
                    object(), str(Path(directory) / "payout.sqlite"),
                )


if __name__ == "__main__":
    unittest.main()
