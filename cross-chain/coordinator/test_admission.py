import tempfile
import unittest
from pathlib import Path

from admission import AdmissionDenied, ReadinessAdmissionGuard
from order_ledger import (
    CrossChainOrderLedger, DestinationPayoutEvidence, OrderQuote,
    SourceDepositEvidence,
)


class FakeMonitor:
    def __init__(self, ready=True):
        self.ready = ready
        self.calls = []
        self.raise_error = False

    def admission(self, source, destination):
        self.calls.append((source, destination))
        if self.raise_error:
            raise TimeoutError("local monitor unavailable")
        return self.ready, {"admissible": self.ready}


class AdmissionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CrossChainOrderLedger(str(Path(self.temp.name) / "orders.sqlite"))
        self.monitor = FakeMonitor()
        self.guard = ReadinessAdmissionGuard(self.monitor, self.ledger)
        self.quote = OrderQuote(
            order_id="order-guard-001", source_chain="ethereum",
            source_asset="0x" + "33"*20, source_amount=25_000_000,
            user="0x" + "22"*20, solver="0x" + "44"*20,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55"*20, destination_amount=10**18,
            quote_expiry=2_000_000_000, refund_after=2_000_003_600,
        )
        self.deposit = SourceDepositEvidence(
            order_id=self.quote.order_id, source_chain="ethereum",
            transaction_id="0x" + "aa"*32, event_index=1,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:100",
        )
        self.payout = DestinationPayoutEvidence(
            order_id=self.quote.order_id, transaction_id="0x" + "bb"*32,
            event_index=2, destination_chain_id=self.quote.destination_chain_id,
            source_chain="ethereum", source_asset=self.quote.source_asset,
            source_amount=self.quote.source_amount, recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount, solver=self.quote.solver,
            finalized_reference="sobya:finalized:200",
        )

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_ready_networks_allow_quote_and_deposit(self):
        self.guard.register_quote(self.quote, now=1_900_000_000)
        self.guard.record_source_deposit(self.deposit, now=1_900_000_001)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "SOURCE_FUNDED")
        self.assertEqual(self.monitor.calls, [("ethereum", "sobya"), ("ethereum", "sobya")])

    def test_unhealthy_source_or_destination_denies_quote(self):
        self.monitor.ready = False
        with self.assertRaises(AdmissionDenied):
            self.guard.register_quote(self.quote, now=1_900_000_000)
        with self.assertRaisesRegex(Exception, "unknown order"):
            self.ledger.get_order(self.quote.order_id)

    def test_readiness_loss_denies_source_deposit(self):
        self.guard.register_quote(self.quote, now=1_900_000_000)
        self.monitor.ready = False
        with self.assertRaises(AdmissionDenied):
            self.guard.record_source_deposit(self.deposit, now=1_900_000_001)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "QUOTED")

    def test_monitor_timeout_fails_closed(self):
        self.monitor.raise_error = True
        with self.assertRaises(AdmissionDenied):
            self.guard.register_quote(self.quote, now=1_900_000_000)

    def test_missing_source_fails_closed(self):
        with self.assertRaises(AdmissionDenied):
            self.guard._require_ready(" ")

    def test_existing_order_completion_not_blocked_by_admission_pause(self):
        self.guard.register_quote(self.quote, now=1_900_000_000)
        self.guard.record_source_deposit(self.deposit, now=1_900_000_001)
        self.monitor.ready = False
        self.guard.record_destination_payout(self.payout, now=1_900_000_002)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "DESTINATION_PAID")

    def test_readiness_exception_does_not_change_existing_order(self):
        self.guard.register_quote(self.quote, now=1_900_000_000)
        self.monitor.raise_error = True
        with self.assertRaises(AdmissionDenied):
            self.guard.record_source_deposit(self.deposit, now=1_900_000_001)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "QUOTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
