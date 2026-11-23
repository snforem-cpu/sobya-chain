import os
import tempfile
import unittest
from pathlib import Path

from custodial_ledger import CustodialOrderLedger
from payout_executor import (
    InventoryPayoutExecutor, PayoutError, PayoutJournal, PayoutPending,
    PayoutIntent, PreparedPayout,
)


class MockAdapter:
    network = "sobya"
    def __init__(self):
        self.prepares = 0
        self.broadcasts = []
        self.finalized = False
    def prepare(self, intent):
        self.prepares += 1
        return PreparedPayout("0x" + "ab" * 32, b"signed-raw-transaction")
    def broadcast(self, prepared):
        self.broadcasts.append(prepared.signed_payload)
        return prepared.tx_id
    def verify_finalized(self, intent, tx_id):
        return self.finalized


class PayoutExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.ledger = CustodialOrderLedger(root / "orders.sqlite")
        self.order = self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum", destination_network="sobya",
            deposit_address="0xInventory", source_wallet="0xSender",
            destination_wallet="0xRecipient", source_asset="USDT-ETH",
            destination_asset="SOBY", source_amount=1_000_000,
            destination_amount=200_000_000_000_000_000,
        )
        self.ledger.record_deposit(
            self.order, tx_id="0x" + "11" * 32, event_index=1,
            observed_amount=1_000_000, observed_recipient="0xInventory",
            observed_asset="USDT-ETH",
        )
        self.ledger.confirm_deposit_final(self.order, verified=True)
        self.adapter = MockAdapter()
        self.journal = PayoutJournal(root / "payout.sqlite")
        self.executor = InventoryPayoutExecutor(
            self.ledger, self.journal, {"sobya": self.adapter}, enabled=True
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_runtime_payout_gate_defaults_to_disabled(self):
        disabled = InventoryPayoutExecutor(
            self.ledger, PayoutJournal(Path(self.tmp.name) / "disabled.sqlite"),
            {"sobya": self.adapter},
        )
        with self.assertRaises(PayoutError):
            disabled.execute_or_resume(self.order)
        self.assertEqual(self.adapter.prepares, 0)

    def test_missing_journal_for_submitted_payout_never_creates_replacement(self):
        self.ledger.submit_payout(self.order, payout_tx="0x" + "99" * 32)
        with self.assertRaises(PayoutError):
            self.executor.execute_or_resume(self.order)
        self.assertEqual(self.adapter.prepares, 0)
        self.assertEqual(self.adapter.broadcasts, [])

    def test_completed_order_without_journal_cannot_pay_again(self):
        self.ledger.submit_payout(self.order, payout_tx="0x" + "88" * 32)
        self.ledger.confirm_payout_final(
            self.order, verified=True, observed_amount=200_000_000_000_000_000,
            observed_recipient="0xRecipient", observed_asset="SOBY",
        )
        with self.assertRaises(PayoutError):
            self.executor.execute_or_resume(self.order)
        self.assertEqual(self.adapter.prepares, 0)

    def test_prepare_persist_broadcast_and_finalize(self):
        tx = self.executor.execute_or_resume(self.order)
        self.assertEqual(tx, "0x" + "ab" * 32)
        self.assertEqual(self.ledger.get_order(self.order)["state"], "payout_submitted")
        self.assertEqual(self.journal.get(self.order)["state"], "broadcast")
        self.adapter.finalized = True
        self.assertTrue(self.executor.confirm_finalized(self.order))
        self.assertEqual(self.ledger.get_order(self.order)["state"], "complete")
        self.assertEqual(self.journal.get(self.order)["state"], "finalized")

    def test_retry_rebroadcasts_same_signed_transaction_without_resigning(self):
        self.executor.execute_or_resume(self.order)
        self.executor.execute_or_resume(self.order)
        self.assertEqual(self.adapter.prepares, 1)
        self.assertEqual(self.adapter.broadcasts, [b"signed-raw-transaction"] * 2)
        self.assertEqual(self.ledger.get_order(self.order)["payout_tx"], "0x" + "ab" * 32)

    def test_broadcast_uncertainty_keeps_signed_transaction_for_safe_retry(self):
        original = self.adapter.broadcast
        def uncertain(prepared):
            self.adapter.broadcasts.append(prepared.signed_payload)
            raise TimeoutError("simulated timeout")
        self.adapter.broadcast = uncertain
        with self.assertRaises(PayoutPending):
            self.executor.execute_or_resume(self.order)
        self.assertEqual(self.journal.get(self.order)["state"], "prepared")
        self.adapter.broadcast = original
        self.executor.execute_or_resume(self.order)
        self.assertEqual(self.adapter.prepares, 1)

    def test_cannot_pay_before_finalized_deposit(self):
        other = self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum", destination_network="sobya",
            deposit_address="0xInventory", source_wallet="0xSender",
            destination_wallet="0xOther", source_asset="USDT-ETH",
            destination_asset="SOBY", source_amount=1_000_000, destination_amount=2,
        )
        with self.assertRaises(PayoutError):
            self.executor.execute_or_resume(other)
        self.assertIsNone(self.journal.get(other))

    def test_finality_required_before_order_complete(self):
        self.executor.execute_or_resume(self.order)
        with self.assertRaises(PayoutPending):
            self.executor.confirm_finalized(self.order)
        self.assertEqual(self.ledger.get_order(self.order)["state"], "payout_submitted")

    def test_journal_is_owner_only(self):
        mode = self.journal.path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
