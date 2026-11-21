import unittest

from order_state import (
    DepositProof, Order, OrderBook, OrderError, OrderState, PayoutProof,
)


class OrderStateTests(unittest.TestCase):
    def setUp(self):
        self.book = OrderBook()
        self.order = Order(
            order_id="order-001", source_chain="ethereum",
            source_asset="0xUSDT", source_escrow="0xESCROW",
            source_sender="0xUSER", source_amount=25_000_000,
            destination_chain_id=357812033857,
            destination_recipient="0xSOBYAUSER", destination_amount=10**18,
            solver="solver-A", quote_expiry=1_000, refund_after=2_000,
        )
        self.book.create(self.order, now=100)

    def commit(self):
        return self.book.commit("order-001", "solver-A", now=200)

    def deposit(self, **overrides):
        values = dict(
            chain="ethereum", asset="0xUSDT", escrow="0xESCROW",
            sender="0xUSER", amount=25_000_000, order_id="order-001",
            transaction_id="0xtx-1", finalized=True, verifier_id="observer-1",
        )
        values.update(overrides)
        return DepositProof(**values)

    def payout(self, **overrides):
        values = dict(
            destination_chain_id=357812033857, recipient="0xSOBYAUSER",
            amount=10**18, order_id="order-001", transaction_id="0xsoby-1",
            finalized=True, verifier_id="observer-2",
        )
        values.update(overrides)
        return PayoutProof(**values)

    def test_happy_path_requires_final_source_and_destination_proofs(self):
        self.commit()
        self.assertEqual(self.book.record_deposit("order-001", self.deposit()).state, OrderState.SOURCE_FINAL)
        self.assertEqual(self.book.record_destination_payout("order-001", self.payout()).state, OrderState.DESTINATION_PAID)
        self.assertEqual(self.book.complete_solver_claim("order-001").state, OrderState.COMPLETE)

    def test_duplicate_order_id_rejected(self):
        with self.assertRaisesRegex(OrderError, "ORDER_ID_EMPTY_OR_ALREADY_USED"):
            self.book.create(self.order, now=100)

    def test_wrong_solver_cannot_commit(self):
        with self.assertRaisesRegex(OrderError, "SOLVER_MISMATCH"):
            self.book.commit("order-001", "attacker", now=200)

    def test_expired_quote_cannot_be_committed(self):
        result = self.book.commit("order-001", "solver-A", now=1_000)
        self.assertEqual(result.state, OrderState.EXPIRED)

    def test_non_final_deposit_rejected(self):
        self.commit()
        with self.assertRaisesRegex(OrderError, "DEPOSIT_NOT_INDEPENDENTLY_FINALIZED"):
            self.book.record_deposit("order-001", self.deposit(finalized=False))

    def test_wrong_token_or_sender_rejected(self):
        self.commit()
        with self.assertRaisesRegex(OrderError, "DEPOSIT_PROOF_BINDING_MISMATCH"):
            self.book.record_deposit("order-001", self.deposit(sender="0xATTACKER"))

    def test_duplicate_source_transaction_cannot_fund_two_orders(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        second = Order(**{**self.order.__dict__, "order_id": "order-002"})
        self.book.create(second, now=100)
        self.book.commit("order-002", "solver-A", now=200)
        duplicate = self.deposit(order_id="order-002")
        with self.assertRaisesRegex(OrderError, "DEPOSIT_ALREADY_CONSUMED"):
            self.book.record_deposit("order-002", duplicate)

    def test_payout_cannot_precede_final_deposit(self):
        self.commit()
        with self.assertRaisesRegex(OrderError, "SOURCE_DEPOSIT_NOT_FINAL"):
            self.book.record_destination_payout("order-001", self.payout())

    def test_wrong_destination_or_amount_rejected(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        with self.assertRaisesRegex(OrderError, "PAYOUT_PROOF_BINDING_MISMATCH"):
            self.book.record_destination_payout("order-001", self.payout(amount=1))

    def test_unfinalized_payout_rejected(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        with self.assertRaisesRegex(OrderError, "PAYOUT_NOT_INDEPENDENTLY_FINALIZED"):
            self.book.record_destination_payout("order-001", self.payout(finalized=False))

    def test_solver_cannot_claim_before_final_payout(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        with self.assertRaisesRegex(OrderError, "SOLVER_CLAIM_REQUIRES_FINAL_PAYOUT"):
            self.book.complete_solver_claim("order-001")

    def test_refund_before_deadline_rejected(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        with self.assertRaisesRegex(OrderError, "REFUND_DEADLINE_NOT_REACHED"):
            self.book.refund_user("order-001", now=1_999)

    def test_refund_after_deadline_is_terminal_and_blocks_claim(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        self.assertEqual(self.book.refund_user("order-001", now=2_000).state, OrderState.REFUNDED)
        with self.assertRaisesRegex(OrderError, "ORDER_NOT_REFUNDABLE"):
            self.book.refund_user("order-001", now=2_001)
        with self.assertRaisesRegex(OrderError, "SOLVER_CLAIM_REQUIRES_FINAL_PAYOUT"):
            self.book.complete_solver_claim("order-001")

    def test_completed_order_cannot_be_refunded(self):
        self.commit()
        self.book.record_deposit("order-001", self.deposit())
        self.book.record_destination_payout("order-001", self.payout())
        self.book.complete_solver_claim("order-001")
        with self.assertRaisesRegex(OrderError, "ORDER_NOT_REFUNDABLE"):
            self.book.refund_user("order-001", now=3_000)

    def test_unfunded_order_cannot_call_refund(self):
        self.commit()
        with self.assertRaisesRegex(OrderError, "ORDER_NOT_REFUNDABLE"):
            self.book.refund_user("order-001", now=2_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
