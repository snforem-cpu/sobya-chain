import tempfile
import unittest
from pathlib import Path

from admission import ReadinessAdmissionGuard
from coordinator import LocalCoordinator, VerificationRejected
from order_ledger import (
    CrossChainOrderLedger, DestinationPayoutEvidence, OrderQuote,
    SourceDepositEvidence,
)
from test_admission import FakeMonitor


class LocalCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CrossChainOrderLedger(str(Path(self.temp.name) / "orders.sqlite"))
        self.solver = "0x" + "44" * 20
        self.ledger.set_solver_inventory(self.solver, 3 * 10**18)
        self.monitor = FakeMonitor()
        self.service = LocalCoordinator(
            ReadinessAdmissionGuard(self.monitor, self.ledger),
            inventory_guard=lambda _quote: True,
            reserve_onchain_inventory=lambda _quote: True,
        )
        self.quote = OrderQuote(
            order_id="coordinator-order-001", source_chain="ethereum",
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

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_quote_requires_positive_signature_verification(self):
        with self.assertRaises(VerificationRejected):
            self.service.issue_quote(self.quote, b"sig", lambda *_: False, now=1_900_000_000)
        with self.assertRaisesRegex(Exception, "unknown order"):
            self.ledger.get_order(self.quote.order_id)
        self.service.issue_quote(self.quote, b"sig", lambda q, sig: q == self.quote and sig == b"sig",
                                 now=1_900_000_000)
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), 2 * 10**18)

    def test_quote_fails_closed_without_inventory_reconciliation(self):
        service = LocalCoordinator(ReadinessAdmissionGuard(self.monitor, self.ledger))
        with self.assertRaises(VerificationRejected):
            service.issue_quote(
                self.quote, b"sig", lambda *_: True, now=1_900_000_000
            )

    def test_quote_fails_closed_without_finalized_vault_reservation(self):
        service = LocalCoordinator(
            ReadinessAdmissionGuard(self.monitor, self.ledger),
            inventory_guard=lambda _quote: True,
        )
        with self.assertRaises(VerificationRejected):
            service.issue_quote(self.quote, b"sig", lambda *_: True, now=1_900_000_000)
        with self.assertRaisesRegex(Exception, "unknown order"):
            self.ledger.get_order(self.quote.order_id)

    def test_failed_vault_reservation_never_registers_quote(self):
        service = LocalCoordinator(
            ReadinessAdmissionGuard(self.monitor, self.ledger),
            inventory_guard=lambda _quote: True,
            reserve_onchain_inventory=lambda _quote: False,
        )
        with self.assertRaises(VerificationRejected):
            service.issue_quote(self.quote, b"sig", lambda *_: True, now=1_900_000_000)
        with self.assertRaisesRegex(Exception, "unknown order"):
            self.ledger.get_order(self.quote.order_id)

    def test_source_deposit_requires_positive_observer_verification(self):
        self.service.issue_quote(self.quote, b"sig", lambda *_: True, now=1_900_000_000)
        with self.assertRaises(VerificationRejected):
            self.service.accept_source_deposit(self.deposit, {"finalized": True},
                                               lambda *_: False, now=1_900_000_001)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "QUOTED")
        self.service.accept_source_deposit(self.deposit, {"finalized": True},
                                           lambda evidence, proof: proof == {"finalized": True},
                                           now=1_900_000_001)
        self.assertEqual(self.ledger.get_order(self.quote.order_id)["status"], "SOURCE_FUNDED")

    def test_verifier_exception_fails_closed(self):
        def broken(*_):
            raise TimeoutError("observer unavailable")
        with self.assertRaises(VerificationRejected):
            self.service.issue_quote(self.quote, b"sig", broken, now=1_900_000_000)
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), 3 * 10**18)


if __name__ == "__main__":
    unittest.main(verbosity=2)
