import tempfile
import unittest
from pathlib import Path

from custodial_ledger import CustodialOrderLedger
from order_api import CustodialOrderApi, OrderApiError


class FakeDepositWorker:
    def __init__(self):
        self.submissions = []

    def submit(self, order_id, tx_id, event_index):
        self.submissions.append((order_id, tx_id, event_index))


def api_config():
    return {
        "mode": "custodial-inventory",
        "depositWatchEnabled": True,
        "networks": {
            "ethereum": {"depositWatchEnabled": True, "usdtContract": "0x" + "11" * 20,
                         "inventoryWallet": "0x" + "22" * 20, "inventoryVerified": True},
            "tron": {"depositWatchEnabled": True, "usdtContract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                     "inventoryWallet": "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx", "inventoryVerified": True},
            "solana": {"depositWatchEnabled": True, "usdtContract": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                       "inventoryWallet": "InventoryOwner111111111111111111111111111", "inventoryVerified": True},
            "sobya": {"depositWatchEnabled": True, "inventoryWallet": "0x" + "33" * 20, "inventoryVerified": True},
        },
        "pricing": {"baseReferencePriceUsdtPerSoby": "0.005"},
        "limits": {"quoteLifetimeSeconds": 120, "feeBps": 0},
    }


class OrderApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = CustodialOrderLedger(Path(self.tmp.name) / "orders.sqlite")
        self.worker = FakeDepositWorker()
        self.now = [1000]
        self.api = CustodialOrderApi(self.ledger, self.worker, api_config(),
                                     clock=lambda: self.now[0])

    def test_usdt_to_soby_quote_uses_shared_inventory_and_integer_units(self):
        quote = self.api.create_quote({
            "direction": "usdt_to_soby", "source_network": "ethereum",
            "destination_network": "sobya", "source_wallet": "0x" + "44" * 20,
            "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": 1_000_000,
        })
        self.assertEqual(quote["deposit_address"], "0x" + "22" * 20)
        self.assertEqual(quote["destination_amount_base_units"], "200000000000000000")
        self.assertEqual(quote["quote_expires_at"], 1120)
        self.assertEqual(self.ledger.get_order(quote["order_id"])["state"], "created")

    def test_soby_to_usdt_quote_uses_sobya_inventory_and_selected_chain(self):
        quote = self.api.create_quote({
            "direction": "soby_to_usdt", "source_network": "sobya",
            "destination_network": "tron", "source_wallet": "0x" + "44" * 20,
            "destination_wallet": "TUserAddress", "source_amount_base_units": 10**18,
        })
        self.assertEqual(quote["deposit_address"], "0x" + "33" * 20)
        self.assertEqual(quote["destination_asset"], "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
        self.assertEqual(quote["destination_amount_base_units"], "5000")

    def test_deposit_proof_is_bound_to_order_and_exact_event_index(self):
        quote = self.api.create_quote({
            "direction": "usdt_to_soby", "source_network": "tron",
            "destination_network": "sobya", "source_wallet": "TUserAddress",
            "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": 2_000_000,
        })
        result = self.api.submit_deposit(quote["order_id"], {
            "transaction_id": "ab" * 32, "event_index": 3,
        })
        self.assertEqual(result["status"], "deposit_submitted")
        self.assertEqual(self.worker.submissions, [(quote["order_id"], "ab" * 32, 3)])

    def test_expired_quote_cannot_submit_deposit(self):
        quote = self.api.create_quote({
            "direction": "usdt_to_soby", "source_network": "ethereum",
            "destination_network": "sobya", "source_wallet": "0x" + "44" * 20,
            "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": 1_000_000,
        })
        self.now[0] = quote["quote_expires_at"]
        with self.assertRaisesRegex(OrderApiError, "quote expired"):
            self.api.submit_deposit(quote["order_id"], {"transaction_id": "0x" + "aa" * 32, "event_index": 0})
        self.assertEqual(self.worker.submissions, [])

    def test_bad_event_index_rejected_before_queue(self):
        quote = self.api.create_quote({
            "direction": "usdt_to_soby", "source_network": "ethereum",
            "destination_network": "sobya", "source_wallet": "0x" + "44" * 20,
            "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": 1_000_000,
        })
        with self.assertRaisesRegex(OrderApiError, "event_index"):
            self.api.submit_deposit(quote["order_id"], {"transaction_id": "0x" + "aa" * 32, "event_index": -1})

    def test_disabled_source_watcher_rejects_quote(self):
        cfg = api_config()
        cfg["networks"]["solana"]["depositWatchEnabled"] = False
        api = CustodialOrderApi(self.ledger, self.worker, cfg, clock=lambda: self.now[0])
        with self.assertRaisesRegex(OrderApiError, "not enabled"):
            api.create_quote({
                "direction": "usdt_to_soby", "source_network": "solana",
                "destination_network": "sobya", "source_wallet": "SolanaUser",
                "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": 1_000_000,
            })

    def test_zero_or_non_integer_amount_rejected(self):
        for amount in (0, -1, 1.5, True, "100"):
            with self.assertRaises(OrderApiError):
                self.api.create_quote({
                    "direction": "usdt_to_soby", "source_network": "ethereum",
                    "destination_network": "sobya", "source_wallet": "0x" + "44" * 20,
                    "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": amount,
                })

    def test_order_status_exposes_quote_and_current_state(self):
        quote = self.api.create_quote({
            "direction": "usdt_to_soby", "source_network": "ethereum",
            "destination_network": "sobya", "source_wallet": "0x" + "44" * 20,
            "destination_wallet": "0x" + "55" * 20, "source_amount_base_units": 1_000_000,
        })
        status = self.api.get_order(quote["order_id"])
        self.assertEqual(status["status"], "created")
        self.assertEqual(status["quote"]["price_usdt_per_soby"], "0.005")


if __name__ == "__main__":
    unittest.main()
