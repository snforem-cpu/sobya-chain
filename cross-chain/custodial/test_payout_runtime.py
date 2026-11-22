import tempfile
import unittest
from pathlib import Path

from custodial_ledger import CustodialOrderLedger
from payout_runtime import build_inventory_payout_executor


INVENTORY = "0xebdb899fFE84a89e1d576964b640491c135651AD"


def networks(**overrides):
    result = {
        "ethereum": {"enabled": False},
        "tron": {"enabled": False},
        "solana": {"enabled": False},
        "sobya": {"enabled": False, "inventoryWallet": INVENTORY},
    }
    for name, values in overrides.items():
        result[name].update(values)
    return result


class PayoutRuntimeGateTests(unittest.TestCase):
    def build(self, directory, config):
        ledger = CustodialOrderLedger(Path(directory) / "orders.sqlite")
        return build_inventory_payout_executor(
            config, ledger, str(Path(directory) / "payout.sqlite")
        )

    def test_example_disabled_networks_create_no_signing_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            executor = self.build(directory, {
                "mode": "custodial-inventory", "featureEnabled": False,
                "networks": networks(),
            })
            self.assertFalse(executor.enabled)
            self.assertEqual(executor.adapters, {})

    def test_sobya_is_the_only_supported_payout_target(self):
        with tempfile.TemporaryDirectory() as directory:
            executor = self.build(directory, {
                "mode": "custodial-inventory", "featureEnabled": True,
                "networks": networks(),
            })
            # Global enablement cannot activate payouts unless SOBYA itself is enabled.
            self.assertFalse(executor.enabled)
            self.assertEqual(executor.adapters, {})

    def test_ethereum_payout_is_rejected_even_if_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "ethereum payouts are not supported"):
                self.build(directory, {
                    "mode": "custodial-inventory", "featureEnabled": True,
                    "networks": networks(ethereum={"enabled": True}),
                })

    def test_tron_and_solana_payouts_are_rejected(self):
        for name in ("tron", "solana"):
            with self.subTest(network=name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, name + " payouts are not supported"):
                    self.build(directory, {
                        "mode": "custodial-inventory", "featureEnabled": True,
                        "networks": networks(**{name: {"enabled": True}}),
                    })

    def test_sobya_wallet_is_required_when_payouts_are_globally_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "sobya inventory wallet is required"):
                self.build(directory, {
                    "mode": "custodial-inventory", "featureEnabled": True,
                    "networks": {
                        "ethereum": {"enabled": False},
                        "tron": {"enabled": False},
                        "solana": {"enabled": False},
                        "sobya": {"enabled": False},
                    },
                })

    def test_wrong_mode_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.build(directory, {
                    "mode": "solver-escrow", "featureEnabled": False, "networks": {},
                })


if __name__ == "__main__":
    unittest.main()
