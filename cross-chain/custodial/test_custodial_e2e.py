"""Offline end-to-end test for the Ethereum-USDT to SOBYA-SOBY order lifecycle.

All chain-facing components are deterministic fakes. No RPC endpoint, private key,
network broadcast, or real asset transfer is used by this test.
"""
import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection

from custodial_ledger import CustodialOrderLedger
from custodial_order_api import create_server
from custodial_runtime import CustodialDepositPayoutRuntime
from payout_worker import InventoryPayoutWorker


class SimulatedFinalityDepositWorker:
    """Accept API proofs, then simulate an exact finalized Ethereum USDT event."""
    def __init__(self, ledger):
        self.ledger = ledger
        self.pending = []

    def submit(self, order_id, tx_id, event_index):
        self.pending.append((order_id, tx_id, event_index))

    def run_once(self):
        verified = 0
        for order_id, tx_id, event_index in self.pending:
            order = self.ledger.get_order(order_id)
            self.ledger.record_deposit(
                order_id,
                tx_id=tx_id,
                event_index=event_index,
                observed_amount=int(order["source_amount"]),
                observed_recipient=order["deposit_address"],
                observed_asset=order["source_asset"],
            )
            self.ledger.confirm_deposit_final(order_id, verified=True)
            verified += 1
        self.pending.clear()
        return {"verified": verified, "pending": 0, "failed": 0}


class SimulatedFinalityPayoutExecutor:
    """Simulate a payout adapter while preserving the real worker/ledger states."""
    enabled = True

    def __init__(self, ledger):
        self.ledger = ledger

    def execute_or_resume(self, order_id):
        self.ledger.submit_payout(order_id, payout_tx="0x" + "ab" * 32)

    def confirm_finalized(self, order_id):
        order = self.ledger.get_order(order_id)
        if order["state"] == "payout_submitted":
            self.ledger.confirm_payout_final(
                order_id,
                verified=True,
                observed_amount=int(order["destination_amount"]),
                observed_recipient=order["destination_wallet"],
                observed_asset=order["destination_asset"],
            )
            return True
        return order["state"] == "complete"


class CustodialEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CustodialOrderLedger(self.temp.name + "/orders.sqlite")
        self.deposit_worker = SimulatedFinalityDepositWorker(self.ledger)
        self.payout_worker = InventoryPayoutWorker(
            self.ledger, SimulatedFinalityPayoutExecutor(self.ledger)
        )
        self.runtime = CustodialDepositPayoutRuntime(
            self.ledger, self.deposit_worker, self.payout_worker
        )
        self.config = {
            "enabledSwapDirections": ["usdt_to_soby"],
            "enabledSourceNetworks": ["ethereum"],
            "networks": {
                "ethereum": {
                    "inventoryWallet": "0x" + "11" * 20,
                    "usdtContract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                    "payoutInventoryVerified": True,
                },
                "tron": {
                    "inventoryWallet": "T" + "1" * 33,
                    "usdtContract": "T" + "2" * 33,
                    "payoutInventoryVerified": False,
                },
                "solana": {
                    "inventoryWallet": "S" * 44,
                    "usdtMint": "M" * 44,
                    "payoutInventoryVerified": False,
                },
                "sobya": {
                    "inventoryWallet": "0x" + "22" * 20,
                    "payoutInventoryVerified": True,
                },
            },
        }

        def quote(_direction, _network, _amount):
            return {
                "destination_amount": 24_750_000_000_000_000_000,
                "rate": "0.005",
                "fee_bps": 100,
                "expires_at": int(time.time()) + 300,
                "executable": True,
            }

        self.server = create_server(
            "127.0.0.1", 0, self.ledger, self.deposit_worker,
            config=self.config, quote_provider=quote, access_secret="test-secret-" + "x" * 48,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def post(self, path, payload, token=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request("POST", path, json.dumps(payload), headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        connection.close()
        return response.status, result

    def test_order_moves_from_creation_to_finalized_payout(self):
        request = {
            "direction": "usdt_to_soby",
            "source_network": "ethereum",
            "amount": "25",
            "source_wallet": "0x" + "33" * 20,
            "destination_wallet": "0x" + "44" * 20,
        }
        status, created = self.post("/api/orders", request)
        self.assertEqual(status, 201, created)
        order_id = created["order_id"]
        order_token = created["order_token"]
        self.assertEqual(created["deposit_address"], self.config["networks"]["ethereum"]["inventoryWallet"])
        self.assertEqual(self.ledger.get_order(order_id)["state"], "created")

        status, proof = self.post(
            "/api/orders/" + order_id + "/deposit-proof",
            {"tx_id": "0x" + "55" * 32, "event_index": 0},
            order_token,
        )
        self.assertEqual(status, 202, proof)
        self.assertEqual(self.ledger.get_order(order_id)["state"], "created")

        cycle = self.runtime.run_once()
        self.assertEqual(cycle["deposits"]["verified"], 1)
        self.assertEqual(cycle["payouts"]["submitted"], 1)
        self.assertEqual(cycle["payouts"]["finalized"], 1)

        final_order = self.ledger.get_order(order_id)
        self.assertEqual(final_order["state"], "complete")
        self.assertEqual(final_order["deposit_tx"], "0x" + "55" * 32)
        self.assertEqual(final_order["payout_tx"], "0x" + "ab" * 32)
        self.assertEqual(int(final_order["destination_amount"]), 24_750_000_000_000_000_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
