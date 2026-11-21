import unittest

from payout_worker import InventoryPayoutWorker
from payout_executor import PayoutError, PayoutPending


class FakeLedger:
    def __init__(self, orders):
        self.orders = orders
    def list_orders(self, *, states, limit):
        return [o for o in self.orders if o["state"] in states][:limit]


class FakeExecutor:
    enabled = True
    def __init__(self):
        self.submitted = []
        self.checked = []
        self.pending = set()
        self.errors = set()
    def execute_or_resume(self, order_id):
        self.submitted.append(order_id)
        if order_id in self.pending:
            raise PayoutPending("not finalized")
        if order_id in self.errors:
            raise PayoutError("held")
        return "tx"
    def confirm_finalized(self, order_id):
        self.checked.append(order_id)
        if order_id in self.pending:
            raise PayoutPending("not finalized")
        if order_id in self.errors:
            raise PayoutError("held")
        return True


class PayoutWorkerTests(unittest.TestCase):
    def test_worker_drains_only_finalized_and_submitted_orders(self):
        ledger = FakeLedger([
            {"order_id": "a", "state": "deposit_final"},
            {"order_id": "b", "state": "payout_submitted"},
            {"order_id": "c", "state": "created"},
            {"order_id": "d", "state": "complete"},
        ])
        executor = FakeExecutor()
        result = InventoryPayoutWorker(ledger, executor).run_once()
        self.assertEqual(executor.submitted, ["a"])
        self.assertEqual(executor.checked, ["a", "b"])
        self.assertEqual(result["submitted"], 1)
        self.assertEqual(result["finalized"], 2)

    def test_worker_keeps_pending_orders_for_next_restart_safe_cycle(self):
        ledger = FakeLedger([{"order_id": "a", "state": "deposit_final"}])
        executor = FakeExecutor()
        executor.pending.add("a")
        result = InventoryPayoutWorker(ledger, executor).run_once()
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["errors"], 0)

    def test_worker_fails_closed_and_continues_other_orders(self):
        ledger = FakeLedger([
            {"order_id": "bad", "state": "deposit_final"},
            {"order_id": "good", "state": "deposit_final"},
        ])
        executor = FakeExecutor()
        executor.errors.add("bad")
        result = InventoryPayoutWorker(ledger, executor).run_once()
        self.assertEqual(result["errors"], 1)
        self.assertIn("good", executor.submitted)

    def test_disabled_executor_never_reads_orders_or_signs(self):
        class Disabled:
            enabled = False
        class NoReadLedger:
            def list_orders(self, **_kwargs):
                raise AssertionError("disabled worker must not read or pay")
        result = InventoryPayoutWorker(NoReadLedger(), Disabled()).run_once()
        self.assertEqual(result["disabled"], 1)


if __name__ == "__main__":
    unittest.main()
