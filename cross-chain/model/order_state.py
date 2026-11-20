"""Reference state machine for cross-chain swap escrow.

This module is a local simulation model, NOT production escrow or proof verification.
Callers must supply independently verified, finalized proofs in a real integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class OrderState(str, Enum):
    QUOTED = "QUOTED"
    COMMITTED = "COMMITTED"
    SOURCE_FUNDED = "SOURCE_FUNDED"
    SOURCE_FINAL = "SOURCE_FINAL"
    DESTINATION_PAID = "DESTINATION_PAID"
    COMPLETE = "COMPLETE"
    REFUNDED = "REFUNDED"
    EXPIRED = "EXPIRED"


class OrderError(ValueError):
    """Raised when an order transition violates a safety invariant."""


@dataclass(frozen=True)
class Order:
    order_id: str
    source_chain: str
    source_asset: str
    source_escrow: str
    source_sender: str
    source_amount: int
    destination_chain_id: int
    destination_recipient: str
    destination_amount: int
    solver: str
    quote_expiry: int
    refund_after: int
    state: OrderState = OrderState.QUOTED
    source_tx_id: Optional[str] = None
    destination_tx_id: Optional[str] = None


@dataclass(frozen=True)
class DepositProof:
    chain: str
    asset: str
    escrow: str
    sender: str
    amount: int
    order_id: str
    transaction_id: str
    finalized: bool
    verifier_id: str


@dataclass(frozen=True)
class PayoutProof:
    destination_chain_id: int
    recipient: str
    amount: int
    order_id: str
    transaction_id: str
    finalized: bool
    verifier_id: str


class OrderBook:
    """In-memory state model with idempotency and mutually exclusive outcomes.

    This intentionally does not persist state, verify cryptographic proofs, call RPCs,
    sign transactions, or custody assets. It is suitable for deterministic unit tests.
    """

    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._used_deposits: Dict[tuple[str, str], str] = {}

    def create(self, order: Order, now: int) -> Order:
        if not order.order_id or order.order_id in self._orders:
            raise OrderError("ORDER_ID_EMPTY_OR_ALREADY_USED")
        if order.source_chain not in {"tron", "ethereum", "solana"}:
            raise OrderError("UNSUPPORTED_SOURCE_CHAIN")
        required = (
            order.source_asset, order.source_escrow, order.source_sender,
            order.destination_recipient, order.solver,
        )
        if any(not value for value in required):
            raise OrderError("MISSING_ORDER_BINDING")
        if min(order.source_amount, order.destination_amount, order.destination_chain_id) <= 0:
            raise OrderError("INVALID_AMOUNT_OR_DESTINATION_CHAIN")
        if order.quote_expiry <= now or order.refund_after <= order.quote_expiry:
            raise OrderError("INVALID_ORDER_DEADLINES")
        if order.state is not OrderState.QUOTED:
            raise OrderError("NEW_ORDER_MUST_BE_QUOTED")
        self._orders[order.order_id] = order
        return order

    def get(self, order_id: str) -> Order:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise OrderError("UNKNOWN_ORDER") from exc

    def commit(self, order_id: str, solver: str, now: int) -> Order:
        order = self.get(order_id)
        if order.state is not OrderState.QUOTED:
            raise OrderError("ORDER_NOT_QUOTED")
        if now >= order.quote_expiry:
            return self._replace(order, state=OrderState.EXPIRED)
        if solver != order.solver:
            raise OrderError("SOLVER_MISMATCH")
        return self._replace(order, state=OrderState.COMMITTED)

    def record_deposit(self, order_id: str, proof: DepositProof) -> Order:
        order = self.get(order_id)
        if order.state is not OrderState.COMMITTED:
            raise OrderError("ORDER_NOT_COMMITTED")
        if not proof.finalized or not proof.verifier_id:
            raise OrderError("DEPOSIT_NOT_INDEPENDENTLY_FINALIZED")
        expected = (
            proof.chain == order.source_chain,
            proof.asset.lower() == order.source_asset.lower(),
            proof.escrow.lower() == order.source_escrow.lower(),
            proof.sender.lower() == order.source_sender.lower(),
            proof.amount == order.source_amount,
            proof.order_id == order.order_id,
            bool(proof.transaction_id),
        )
        if not all(expected):
            raise OrderError("DEPOSIT_PROOF_BINDING_MISMATCH")
        key = (proof.chain, proof.transaction_id)
        if key in self._used_deposits:
            raise OrderError("DEPOSIT_ALREADY_CONSUMED")
        self._used_deposits[key] = order_id
        return self._replace(order, state=OrderState.SOURCE_FINAL, source_tx_id=proof.transaction_id)

    def record_destination_payout(self, order_id: str, proof: PayoutProof) -> Order:
        order = self.get(order_id)
        if order.state is not OrderState.SOURCE_FINAL:
            raise OrderError("SOURCE_DEPOSIT_NOT_FINAL")
        if not proof.finalized or not proof.verifier_id:
            raise OrderError("PAYOUT_NOT_INDEPENDENTLY_FINALIZED")
        expected = (
            proof.destination_chain_id == order.destination_chain_id,
            proof.recipient.lower() == order.destination_recipient.lower(),
            proof.amount == order.destination_amount,
            proof.order_id == order.order_id,
            bool(proof.transaction_id),
        )
        if not all(expected):
            raise OrderError("PAYOUT_PROOF_BINDING_MISMATCH")
        return self._replace(
            order, state=OrderState.DESTINATION_PAID,
            destination_tx_id=proof.transaction_id,
        )

    def complete_solver_claim(self, order_id: str) -> Order:
        order = self.get(order_id)
        if order.state is not OrderState.DESTINATION_PAID:
            raise OrderError("SOLVER_CLAIM_REQUIRES_FINAL_PAYOUT")
        return self._replace(order, state=OrderState.COMPLETE)

    def refund_user(self, order_id: str, now: int) -> Order:
        order = self.get(order_id)
        if order.state is not OrderState.SOURCE_FINAL:
            raise OrderError("ORDER_NOT_REFUNDABLE")
        if now < order.refund_after:
            raise OrderError("REFUND_DEADLINE_NOT_REACHED")
        return self._replace(order, state=OrderState.REFUNDED)

    def _replace(self, order: Order, **changes: object) -> Order:
        updated = Order(**{**order.__dict__, **changes})
        self._orders[order.order_id] = updated
        return updated
