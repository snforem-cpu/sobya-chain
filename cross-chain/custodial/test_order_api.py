import tempfile
import unittest
from pathlib import Path
from custodial_ledger import CustodialOrderLedger
from order_api import CustodialOrderApi, OrderApiError

class FakeDepositWorker:
    def __init__(self): self.submissions = []
    def submit(self, order_id, tx_id, event_index): self.submissions.append((order_id, tx_id, event_index))

def api_config():
    return {
        "mode": "custodial-inventory", "featureEnabled": True, "depositWatchEnabled": True,
        "networks": {
            "ethereum": {"enabled": True, "depositWatchEnabled": True, "chainId": 1, "usdtContract": "0x" + "11" * 20, "inventoryWallet": "0x" + "22" * 20, "inventoryVerified": True},
            "sobya": {"enabled": True, "depositWatchEnabled": True, "chainId": 357812033857, "inventoryWallet": "0x" + "33" * 20, "inventoryVerified": True},
        },
        "pricing": {"baseReferencePriceUsdtPerSoby": "0.005", "referenceLiquidityUsdtBaseUnits": 1000000000000, "demandWindowSeconds": 3600, "demandMaxAgeSeconds": 300, "upwardDemandSensitivityBps": 10000, "downwardDemandSensitivityBps": 2500},
        "limits": {"quoteLifetimeSeconds": 120, "feeBps": 100, "maxOrderUsdtBaseUnits": 500000000, "maxDailyUsdtBaseUnitsPerNetwork": 10000000000, "minimumInventoryBaseUnits": "100000000000000000000000"},
    }

class OrderApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ledger = CustodialOrderLedger(Path(self.tmp.name) / "orders.sqlite")
        self.worker = FakeDepositWorker(); self.now = [1000]
        self.api = CustodialOrderApi(self.ledger, self.worker, api_config(), clock=lambda: self.now[0])
        self.api._check_live_inventory = lambda network, amount, recipient: None

    def quote(self, direction="usdt_to_soby", amount=1000000):
        reverse = direction == "soby_to_usdt"
        return self.api.create_quote({"direction": direction, "source_network": "sobya" if reverse else "ethereum", "destination_network": "ethereum" if reverse else "sobya", "source_wallet": "0x" + "44" * 20, "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": amount})

    def test_usdt_to_soby_quote_uses_inventory_and_fee(self):
        quote = self.quote()
        self.assertEqual(quote["deposit_address"], "0x" + "22" * 20)
        self.assertEqual(quote["gross_destination_amount_base_units"], "200000000000000000000")
        self.assertEqual(quote["destination_amount_base_units"], "198000000000000000000")
        self.assertEqual(quote["fee_bps"], 100)
        self.assertEqual(quote["quote_expires_at"], 1120)

    def test_soby_to_usdt_quote_uses_ethereum_inventory_and_fee(self):
        quote = self.quote("soby_to_usdt", "1000000000000000000")
        self.assertEqual(quote["deposit_address"], "0x" + "33" * 20)
        self.assertEqual(quote["destination_asset"], "0x" + "11" * 20)
        self.assertEqual(quote["gross_destination_amount_base_units"], "5000")
        self.assertEqual(quote["destination_amount_base_units"], "4950")

    def test_price_moves_only_after_completed_executed_buy_order(self):
        self.ledger.create_order(order_id="completed-buy", direction="usdt_to_soby", source_network="ethereum", destination_network="sobya", deposit_address="0x"+"22"*20, source_wallet="0x"+"44"*20, destination_wallet="0x"+"55"*20, source_asset="0x"+"11"*20, destination_asset="asobya", source_amount=100000000, destination_amount=19800000000000000000)
        with __import__("sqlite3").connect(self.ledger.database) as db:
            db.execute("UPDATE custodial_orders SET state='deposit_final' WHERE order_id='completed-buy'")
        before = self.api._price_and_fee()[0]
        self.assertEqual(str(before), "0.005")
        with __import__("sqlite3").connect(self.ledger.database) as db:
            db.execute("UPDATE custodial_orders SET state='complete' WHERE order_id='completed-buy'")
        after = self.api._price_and_fee()[0]
        self.assertGreater(after, before)

    def test_decimal_string_base_units_are_accepted_without_float_conversion(self):
        quote = self.quote("soby_to_usdt", "1000000000000000000")
        self.assertEqual(quote["source_amount_base_units"], "1000000000000000000")

    def test_deposit_proof_is_bound_to_exact_event(self):
        quote = self.quote()
        result = self.api.submit_deposit(quote["order_id"], {"transaction_id": "0x" + "aa" * 32, "event_index": 3})
        self.assertEqual(result["status"], "deposit_submitted")
        self.assertEqual(self.worker.submissions, [(quote["order_id"], "0x" + "aa" * 32, 3)])

    def test_expired_quote_cannot_submit_deposit(self):
        quote = self.quote(); self.now[0] = quote["quote_expires_at"]
        with self.assertRaisesRegex(OrderApiError, "quote expired"):
            self.api.submit_deposit(quote["order_id"], {"transaction_id": "0x" + "aa" * 32, "event_index": 0})

    def test_daily_cap_combines_buys_and_sells_on_ethereum(self):
        import sqlite3, time
        self.ledger.create_order(order_id="earlier-buy-orders", direction="usdt_to_soby", source_network="ethereum", destination_network="sobya", deposit_address="0x"+"22"*20, source_wallet="0x"+"44"*20, destination_wallet="0x"+"55"*20, source_asset="0x"+"11"*20, destination_asset="asobya", source_amount=9800000000, destination_amount=1)
        with sqlite3.connect(self.ledger.database) as db:
            db.execute("INSERT INTO custodial_api_quotes(order_id,price_usdt_per_soby,gross_destination_amount,fee_base_units,fee_bps,expires_at,created_at) VALUES(?,?,?,?,?,?,?)", ("earlier-buy-orders","0.005","1","0",100,9999999999,int(time.time())))
        with self.assertRaisesRegex(OrderApiError, "daily Ethereum USDT order limit"):
            self.quote("soby_to_usdt", "100000000000000000000000")

    def test_unverified_inventory_rejects_quote(self):
        self.api._check_live_inventory = lambda network, amount, recipient: (_ for _ in ()).throw(OrderApiError("inventory has not passed verification"))
        with self.assertRaisesRegex(OrderApiError, "inventory has not passed"): self.quote()

    def test_reference_liquidity_missing_pauses_quotes(self):
        self.api.pricing["referenceLiquidityUsdtBaseUnits"] = None
        with self.assertRaisesRegex(OrderApiError, "reference liquidity"): self.quote()

    def test_unsupported_chain_rejected(self):
        payload = {"direction":"usdt_to_soby", "source_network":"tron", "destination_network":"sobya", "source_wallet":"TUser", "destination_wallet":"0x"+"55"*20, "source_amount_base_units":1000000}
        with self.assertRaisesRegex(OrderApiError, "requires Ethereum"): self.api.create_quote(payload)

    def test_invalid_amount_rejected(self):
        for amount in (0, -1, 1.5, True, "1.5", "0"):
            with self.assertRaises(OrderApiError):
                self.api.create_quote({"direction":"usdt_to_soby", "source_network":"ethereum", "destination_network":"sobya", "source_wallet":"0x"+"44"*20, "destination_wallet":"0x"+"55"*20, "source_amount_base_units":amount})

    def test_order_status_exposes_live_quote_metadata(self):
        quote = self.quote(); status = self.api.get_order(quote["order_id"])
        self.assertEqual(status["status"], "created")
        self.assertEqual(status["quote"]["fee_bps"], 100)

if __name__ == "__main__": unittest.main()
