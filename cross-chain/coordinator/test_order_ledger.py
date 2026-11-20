import tempfile
import unittest
from pathlib import Path

from order_ledger import (
    CrossChainOrderLedger, DestinationPayoutEvidence, LedgerError,
    OrderQuote, SourceDepositEvidence,
)


class OrderLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "orders.sqlite")
        self.ledger = CrossChainOrderLedger(self.path)
        self.quote = OrderQuote(
            order_id="order-001", source_chain="ETHEREUM_MAINNET",
            source_asset="0x" + "33"*20, source_amount=25_000_000,
            user="0x" + "22"*20, solver="0x" + "44"*20,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55"*20, destination_amount=10**18,
            quote_expiry=2_000_000_000, refund_after=2_000_003_600,
        )
        self.deposit = SourceDepositEvidence(
            order_id="order-001", source_chain=self.quote.source_chain,
            transaction_id="0x" + "aa"*32, event_index=1,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:12345",
        )
        self.payout = DestinationPayoutEvidence(
            order_id="order-001", transaction_id="0x" + "bb"*32, event_index=2,
            destination_chain_id=self.quote.destination_chain_id,
            source_chain=self.quote.source_chain, source_asset=self.quote.source_asset,
            source_amount=self.quote.source_amount, recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount, solver=self.quote.solver,
            finalized_reference="sobya:confirmed:54321",
        )

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_monotonic_quote_deposit_payout_flow(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        self.assertEqual(self.ledger.get_order("order-001")["status"], "QUOTED")
        self.ledger.record_source_deposit(self.deposit, now=1_900_000_001)
        self.assertEqual(self.ledger.get_order("order-001")["status"], "SOURCE_FUNDED")
        self.ledger.record_destination_payout(self.payout, now=1_900_000_002)
        result = self.ledger.get_order("order-001")
        self.assertEqual(result["status"], "DESTINATION_PAID")
        self.assertEqual(len(result["events"]), 3)

    def test_payout_before_deposit_rejected(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        with self.assertRaisesRegex(LedgerError, "requires a verified source deposit"):
            self.ledger.record_destination_payout(self.payout)

    def test_source_quote_mismatch_rejected(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        bad = SourceDepositEvidence(**{**self.deposit.__dict__, "source_amount": 1})
        with self.assertRaisesRegex(LedgerError, "source_amount"):
            self.ledger.record_source_deposit(bad)
        self.assertEqual(self.ledger.get_order("order-001")["status"], "QUOTED")

    def test_destination_quote_mismatch_rejected(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        self.ledger.record_source_deposit(self.deposit)
        bad = DestinationPayoutEvidence(**{**self.payout.__dict__, "destination_amount": 1})
        with self.assertRaisesRegex(LedgerError, "destination_amount"):
            self.ledger.record_destination_payout(bad)
        self.assertEqual(self.ledger.get_order("order-001")["status"], "SOURCE_FUNDED")

    def test_replayed_source_event_rejected(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        self.ledger.record_source_deposit(self.deposit)
        with self.assertRaisesRegex(LedgerError, "already recorded"):
            self.ledger.record_source_deposit(self.deposit)

    def test_replayed_destination_event_rejected_across_orders(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        self.ledger.record_source_deposit(self.deposit)
        self.ledger.record_destination_payout(self.payout)
        second = OrderQuote(**{**self.quote.__dict__, "order_id": "order-002"})
        self.ledger.register_quote(second, now=1_900_000_000)
        deposit2 = SourceDepositEvidence(**{**self.deposit.__dict__, "order_id": "order-002",
            "transaction_id": "0x" + "cc"*32})
        self.ledger.record_source_deposit(deposit2)
        payout2 = DestinationPayoutEvidence(**{**self.payout.__dict__, "order_id": "order-002"})
        with self.assertRaisesRegex(LedgerError, "replay"):
            self.ledger.record_destination_payout(payout2)

    def test_quote_expiry_and_refund_deadline_invariant(self):
        with self.assertRaisesRegex(LedgerError, "expired"):
            self.ledger.register_quote(self.quote, now=self.quote.quote_expiry)
        bad = OrderQuote(**{**self.quote.__dict__, "refund_after": self.quote.quote_expiry})
        with self.assertRaisesRegex(LedgerError, "invalid or expired"):
            self.ledger.register_quote(bad, now=1_900_000_000)

    def test_persistence_after_reopen(self):
        self.ledger.register_quote(self.quote, now=1_900_000_000)
        self.ledger.record_source_deposit(self.deposit)
        self.ledger.close()
        self.ledger = CrossChainOrderLedger(self.path)
        self.assertEqual(self.ledger.get_order("order-001")["status"], "SOURCE_FUNDED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
