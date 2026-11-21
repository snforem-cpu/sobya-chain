import http.client
import json
import tempfile
import threading
import unittest
from dataclasses import asdict
from pathlib import Path

from admission import ReadinessAdmissionGuard
from coordinator import LocalCoordinator
from http_api import create_server
from pricing import InventoryAwareQuotePricer, PricingConfig
from order_ledger import (
    CrossChainOrderLedger, DestinationPayoutEvidence, OrderQuote,
    SourceDepositEvidence,
)
from test_admission import FakeMonitor


TOKEN = "local-test-token-that-is-longer-than-32-bytes"


class CoordinatorHttpApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CrossChainOrderLedger(str(Path(self.temp.name) / "orders.sqlite"))
        self.solver = "0x" + "44" * 20
        self.ledger.set_solver_inventory(self.solver, 3 * 10**18)
        self.service = LocalCoordinator(ReadinessAdmissionGuard(FakeMonitor(), self.ledger))
        self.quote = OrderQuote(
            order_id="http-order-001", source_chain="ethereum",
            source_asset="0x" + "33"*20, source_amount=20_000_000,
            user="0x" + "22"*20, solver=self.solver,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55"*20, destination_amount=10**18,
            quote_expiry=2_000_000_000, refund_after=2_000_003_600,
        )
        self.deposit = SourceDepositEvidence(
            order_id=self.quote.order_id, source_chain="ethereum",
            transaction_id="0x" + "aa"*32, event_index=0,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:100",
        )
        self.payout = DestinationPayoutEvidence(
            order_id=self.quote.order_id, transaction_id="0x" + "bb"*32,
            event_index=1, destination_chain_id=self.quote.destination_chain_id,
            source_chain="ethereum", source_asset=self.quote.source_asset,
            source_amount=self.quote.source_amount, recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount, solver=self.quote.solver,
            finalized_reference="sobya:finalized:200",
        )
        self.pricer = InventoryAwareQuotePricer(
            PricingConfig(
                usdt_atoms_numerator=2_000_000, fee_bps=100,
                min_source_amount=1_000_000, max_source_amount=10_000_000,
                quote_ttl_seconds=60, refund_grace_seconds=3600,
            ),
            self.ledger, destination_chain_id=357812033857,
            finalized_balance=lambda _solver: 3 * 10**18,
            now=lambda: 1_900_000_000,
        )
        self.server = create_server(
            "127.0.0.1", 0, self.service, bearer_token=TOKEN,
            quote_pricer=self.pricer,
            verify_quote_signature=lambda *_: True,
            verify_source_deposit=lambda *_: True,
            verify_destination_payout=lambda *_: True,
            max_body_bytes=4096,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.ledger.close()
        self.temp.cleanup()

    def post(self, path, payload, token=TOKEN):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        body = payload if isinstance(payload, str) else json.dumps(payload)
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_authentication_required(self):
        status, _ = self.post("/v1/quotes", {}, token=None)
        self.assertEqual(status, 401)

    def test_unsigned_quote_preview_uses_pricing_and_does_not_reserve(self):
        status, body = self.post("/v1/quote-previews", {"request": {
            "order_id": "0x" + "01"*32,
            "source_chain": "ethereum",
            "source_asset": "0x" + "33"*20,
            "source_amount": 2_000_000,
            "user": "0x" + "22"*20,
            "solver": self.solver,
            "destination_recipient": "0x" + "55"*20,
        }})
        self.assertEqual(status, 200, body)
        payload = json.loads(body)
        self.assertFalse(payload["signed"])
        self.assertFalse(payload["reserved"])
        self.assertEqual(payload["quote"]["destination_amount"], 990_000_000_000_000_000)
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), 3 * 10**18)

    def test_quote_preview_rejects_boolean_amount(self):
        status, _ = self.post("/v1/quote-previews", {"request": {
            "order_id": "0x" + "01"*32,
            "source_chain": "ethereum",
            "source_asset": "0x" + "33"*20,
            "source_amount": True,
            "user": "0x" + "22"*20,
            "solver": self.solver,
            "destination_recipient": "0x" + "55"*20,
        }})
        self.assertEqual(status, 400)

    def test_quote_deposit_and_payout_flow(self):
        status, body = self.post("/v1/quotes", {
            "quote": asdict(self.quote), "signature": "abcd",
        })
        self.assertEqual(status, 201, body)
        status, body = self.post("/v1/source-deposits", {
            "evidence": asdict(self.deposit), "proof": {"finalized": True},
        })
        self.assertEqual(status, 200, body)
        status, body = self.post("/v1/destination-payouts", {
            "evidence": asdict(self.payout), "proof": {"finalized": True},
        })
        self.assertEqual(status, 200, body)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "DESTINATION_PAID")
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), 2 * 10**18)

    def test_bad_signature_is_rejected_without_order_creation(self):
        self.server.verify_quote_signature = lambda *_: False
        status, _ = self.post("/v1/quotes", {
            "quote": asdict(self.quote), "signature": "abcd",
        })
        self.assertEqual(status, 422)
        with self.assertRaisesRegex(Exception, "unknown order"):
            self.ledger.get_order(self.quote.order_id)

    def test_oversized_body_is_rejected(self):
        status, _ = self.post("/v1/quotes", " " * 4097)
        self.assertEqual(status, 413)

    def test_unknown_route_and_wrong_method(self):
        status, _ = self.post("/unknown", {})
        self.assertEqual(status, 404)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("GET", "/v1/quotes")
        response = connection.getresponse()
        self.assertEqual(response.status, 405)
        response.read()
        connection.close()

    def test_public_bind_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "loopback only"):
            create_server(
                "0.0.0.0", 8765, self.service, bearer_token=TOKEN,
                verify_quote_signature=lambda *_: True,
                verify_source_deposit=lambda *_: True,
                verify_destination_payout=lambda *_: True,
            )


    def test_expire_quote_endpoint_releases_reserved_inventory(self):
        from dataclasses import replace
        expiring = replace(
            self.quote, order_id="http-expired-order",
            quote_expiry=1, refund_after=2,
        )
        self.ledger.register_quote_with_inventory(expiring, now=0)
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), 2 * 10**18)
        status, body = self.post("/v1/expire-quotes", {"order_id": expiring.order_id})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["status"], "EXPIRED")
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), 3 * 10**18)

if __name__ == "__main__":
    unittest.main(verbosity=2)
