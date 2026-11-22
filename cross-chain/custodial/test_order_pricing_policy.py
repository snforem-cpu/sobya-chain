import os
import tempfile
import time
import unittest
from unittest.mock import patch

from custodial_ledger import CustodialOrderLedger
from custodial_runtime import build_order_quote_provider, DepositRuntimeConfigurationError


class FakeSobyaRpc:
    observed_at = None
    balance = 1_000_000 * 10**18

    def __init__(self, url):
        self.url = url

    def call(self, method, params):
        if method == "eth_chainId":
            return hex(357812033857)
        if method == "eth_getBlockByNumber":
            return {"number": "0x100", "timestamp": hex(self.observed_at or int(time.time()))}
        if method == "eth_getBalance":
            return hex(self.balance)
        raise AssertionError("unexpected RPC method: " + method)


class OrderPricingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CustodialOrderLedger(self.temp.name + "/orders.sqlite")
        os.environ["TEST_SOBYA_RPC"] = "https://rpc.example.invalid"
        FakeSobyaRpc.observed_at = int(time.time())
        FakeSobyaRpc.balance = 1_000_000 * 10**18
        self.config = {
            "pricing": {
                "baseReferencePriceUsdtPerSoby": "0.005",
                "referenceLiquidityUsdtBaseUnits": 5_000_000_000,
                "demandWindowSeconds": 3600, "demandMaxAgeSeconds": 300,
                "upwardDemandSensitivityBps": 10000, "downwardDemandSensitivityBps": 2500,
                "priceFloor": "0.004", "priceCeiling": "0.01",
                "inventorySnapshotMaxAgeSeconds": 300,
            },
            "limits": {
                "maxOrderUsdtBaseUnits": 100_000_000,
                "maxDailyUsdtBaseUnitsPerNetwork": 500_000_000,
                "minimumInventoryBaseUnits": 100 * 10**18,
                "feeBps": 100, "quoteLifetimeSeconds": 120,
            },
            "networks": {"sobya": {
                "chainId": 357812033857,
                "rpcUrlEnv": "TEST_SOBYA_RPC",
                "inventoryWallet": "0x" + "33" * 20,
            }},
        }

    def tearDown(self):
        os.environ.pop("TEST_SOBYA_RPC", None)
        self.temp.cleanup()

    def provider(self):
        with patch("custodial_runtime.JsonRpc", FakeSobyaRpc):
            return build_order_quote_provider(self.config, self.ledger)

    def test_quote_applies_fee_and_returns_expiry(self):
        quote = self.provider()("usdt_to_soby", "ethereum", 1_000_000)
        self.assertEqual(quote["fee_bps"], 100)
        self.assertEqual(quote["destination_amount"], 198 * 10**18)
        self.assertTrue(quote["expires_at"] > int(time.time()))
        self.assertTrue(quote["executable"])
        self.assertEqual(quote["inventory_block"], "0x100")

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

    def test_expired_unfunded_order_releases_daily_and_inventory_reservations(self):
        order_id = self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum", destination_network="sobya",
            deposit_address="0x" + "11" * 20, source_wallet="0x" + "22" * 20,
            destination_wallet="0x" + "33" * 20, source_asset="0x" + "44" * 20,
            destination_asset="native", source_amount=499_500_000,
            destination_amount=900_000 * 10**18,
        )
        with self.ledger._connect() as db:
            db.execute("CREATE TABLE custodial_order_quote_expiry (order_id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)")
            db.execute("INSERT INTO custodial_order_quote_expiry(order_id, expires_at) VALUES (?, ?)",
                       (order_id, int(time.time()) - 1))
        quote = self.provider()("usdt_to_soby", "ethereum", 1_000_000)
        self.assertEqual(quote["destination_amount"], 198 * 10**18)

    def test_rejects_live_inventory_reserve_breach(self):
        FakeSobyaRpc.balance = 101 * 10**18
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "protected minimum"):
            self.provider()("usdt_to_soby", "ethereum", 1_000_000)

    def test_rejects_stale_live_inventory(self):
        FakeSobyaRpc.observed_at = int(time.time()) - 301
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "inventory observation is stale"):
            self.provider()("usdt_to_soby", "ethereum", 1_000_000)

    def test_rejects_missing_operational_limits(self):
        self.config["limits"]["maxOrderUsdtBaseUnits"] = None
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "maximum order"):
            self.provider()

    def test_rejects_out_of_bounds_demand_price(self):
        # Only finalized, completed swaps are included in the demand signal.
        self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum", destination_network="sobya",
            deposit_address="0x" + "11" * 20, source_wallet="0x" + "22" * 20,
            destination_wallet="0x" + "33" * 20, source_asset="0x" + "44" * 20,
            destination_asset="native", source_amount=5_000_000_000,
            destination_amount=1 * 10**18,
        )
        with self.ledger._connect() as db:
            db.execute("UPDATE custodial_orders SET state='complete'")
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "price bounds"):
            self.provider()("usdt_to_soby", "ethereum", 1_000_000)

    def test_rejects_reverse_direction(self):
        with self.assertRaisesRegex(DepositRuntimeConfigurationError, "only USDT-to-SOBY"):
            self.provider()("soby_to_usdt", "sobya", 10**18)

    def test_demand_ignores_uncompleted_orders(self):
        self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum", destination_network="sobya",
            deposit_address="0x" + "11" * 20, source_wallet="0x" + "22" * 20,
            destination_wallet="0x" + "33" * 20, source_asset="0x" + "44" * 20,
            destination_asset="native", source_amount=1_000_000,
            destination_amount=1 * 10**18,
        )
        quote = self.provider()("usdt_to_soby", "ethereum", 1_000_000)
        self.assertEqual(quote["rate"], "0.005")
