import tempfile
import time
import unittest

from custodial_ledger import CustodialOrderLedger
from custodial_runtime import build_order_quote_provider, DepositRuntimeConfigurationError


class OrderPricingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CustodialOrderLedger(self.temp.name + "/orders.sqlite")
        now = int(time.time())
        self.config = {
            "pricing": {
                "baseReferencePriceUsdtPerSoby": "0.005",
                "referenceLiquidityUsdtBaseUnits": 5_000_000_000,
                "demandSnapshot": {
                    "buyUsdtBaseUnits": 0, "sellUsdtBaseUnits": 0,
                    "windowSeconds": 3600, "observedAtEpoch": now, "finalized": True,
                },
                "demandWindowSeconds": 3600, "demandMaxAgeSeconds": 300,
                "upwardDemandSensitivityBps": 10000, "downwardDemandSensitivityBps": 2500,
                "priceFloor": "0.004", "priceCeiling": "0.01",
            },
            "limits": {
                "maxOrderUsdtBaseUnits": 100_000_000,
                "maxDailyUsdtBaseUnitsPerNetwork": 500_000_000,
                "minimumInventoryBaseUnits": 100 * 10**18,
                "feeBps": 100, "quoteLifetimeSeconds": 120,
            },
            "networks": {"sobya": {
                "verifiedPayoutInventoryBaseUnits": 1_000_000 * 10**18,
                "inventoryObservedAtEpoch": now,
            }},
        }

    def tearDown(self):
        self.temp.cleanup()

    def provider(self):
        return build_order_quote_provider(self.config, self.ledger)

    def test_quote_applies_fee_and_returns_expiry(self):
        quote = self.provider()("usdt_to_soby", "ethereum", 1_000_000)
        self.assertEqual(quote["fee_bps"], 100)
        self.assertEqual(quote["destination_amount"], 198 * 10**18)
        self.assertTrue(quote["expires_at"] > int(time.time()))
        self.assertTrue(quote["executable"])

    def test_rejects_order_above_per_order_limit(self):
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "maximum"):
            self.provider()("usdt_to_soby", "ethereum", 100_000_001)

    def test_rejects_daily_network_limit(self):
        self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum", destination_network="sobya",
            deposit_address="0x" + "11" * 20, source_wallet="0x" + "22" * 20,
            destination_wallet="0x" + "33" * 20, source_asset="0x" + "44" * 20,
            destination_asset="native", source_amount=499_500_000,
            destination_amount=1 * 10**18,
        )
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "daily USDT intake"):
            self.provider()("usdt_to_soby", "ethereum", 1_000_000)

    def test_rejects_inventory_reserve_breach(self):
        self.config["networks"]["sobya"]["verifiedPayoutInventoryBaseUnits"] = 101 * 10**18
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "protected minimum"):
            self.provider()("usdt_to_soby", "ethereum", 1_000_000)

    def test_rejects_stale_inventory_snapshot(self):
        self.config["networks"]["sobya"]["inventoryObservedAtEpoch"] = int(time.time()) - 301
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "inventory snapshot"):
            self.provider()

    def test_rejects_missing_operational_limits(self):
        self.config["limits"]["maxOrderUsdtBaseUnits"] = None
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "maximum order"):
            self.provider()

    def test_rejects_out_of_bounds_demand_price(self):
        self.config["pricing"]["demandSnapshot"]["buyUsdtBaseUnits"] = 5_000_000_000
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "price bounds"):
            self.provider()("usdt_to_soby", "ethereum", 1_000_000)

    def test_rejects_reverse_direction(self):
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "only USDT-to-SOBY"):
            self.provider()("soby_to_usdt", "sobya", 10**18)


if __name__ == "__main__":
    unittest.main(verbosity=2)
