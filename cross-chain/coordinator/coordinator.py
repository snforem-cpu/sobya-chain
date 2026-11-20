"""Local coordinator orchestration boundary.

All cryptographic verification is injected and must be implemented by the
chain-specific verifier modules. This module contains no keys, network listener,
transaction broadcaster, or signing capability.
"""
from __future__ import annotations

from typing import Any, Callable

from admission import ReadinessAdmissionGuard
from order_ledger import DestinationPayoutEvidence, OrderQuote, SourceDepositEvidence


class VerificationRejected(RuntimeError):
    """Raised when a quote or chain evidence fails its verifier."""


class LocalCoordinator:
    """Orchestrate verified evidence through readiness and inventory gates."""

    def __init__(self, admission: ReadinessAdmissionGuard):
        self.admission = admission

    @staticmethod
    def _verify(verifier: Callable[..., Any], *args: Any) -> None:
        if not callable(verifier):
            raise VerificationRejected("a chain-specific verifier is required")
        try:
            verified = verifier(*args)
        except Exception as exc:
            raise VerificationRejected("verification failed") from exc
        if verified is not True:
            raise VerificationRejected("verification was not positively established")

    def issue_quote(self, quote: OrderQuote, signature: bytes,
                    verify_quote_signature: Callable[[OrderQuote, bytes], bool],
                    now: int | None = None) -> None:
        """Verify the solver quote, then readiness-gate and reserve SOBY inventory."""
        if not isinstance(signature, bytes) or not signature:
            raise VerificationRejected("signed quote bytes are required")
        self._verify(verify_quote_signature, quote, signature)
        self.admission.register_quote(quote, now=now)

    def expire_unfunded_quote(self, order_id: str, now: int | None = None) -> None:
        """Expire a quote that never received a source deposit."""
        self.admission.expire_unfunded_quote(order_id, now=now)

    def accept_source_deposit(self, evidence: SourceDepositEvidence, proof: Any,
                              verify_source_deposit: Callable[[SourceDepositEvidence, Any], bool],
                              now: int | None = None) -> None:
        """Accept only observer-verified, finalized source deposit evidence."""
        self._verify(verify_source_deposit, evidence, proof)
        self.admission.record_source_deposit(evidence, now=now)

    def record_destination_payout(self, evidence: DestinationPayoutEvidence, proof: Any,
                                  verify_destination_payout: Callable[[DestinationPayoutEvidence, Any], bool],
                                  now: int | None = None) -> None:
        """Verify payout evidence; allow existing-order completion during admission pause."""
        self._verify(verify_destination_payout, evidence, proof)
        self.admission.record_destination_payout(evidence, now=now)
