"""Fail-closed admission guard for new cross-chain orders.

This is an in-process coordinator boundary, not a public HTTP API. Callers must
supply quote signatures/evidence already verified by the appropriate modules.
"""
from __future__ import annotations

from typing import Any

from order_ledger import (
    CrossChainOrderLedger,
    DestinationPayoutEvidence,
    OrderQuote,
    SourceDepositEvidence,
)


class AdmissionDenied(RuntimeError):
    """Raised when fresh source/destination node readiness cannot be proven."""


class ReadinessAdmissionGuard:
    """Gate only new quote/deposit admission; never gate existing-order recovery."""

    def __init__(self, monitor: Any, ledger: CrossChainOrderLedger,
                 destination_network: str = "sobya"):
        if not destination_network or not destination_network.strip():
            raise ValueError("destination network is required")
        self.monitor = monitor
        self.ledger = ledger
        self.destination_network = destination_network.strip().lower()

    def _require_ready(self, source_network: str) -> None:
        if not isinstance(source_network, str) or not source_network.strip():
            raise AdmissionDenied("source network is missing")
        source = source_network.strip().lower()
        try:
            ready, evidence = self.monitor.admission(source, self.destination_network)
        except Exception as exc:
            raise AdmissionDenied("readiness check failed; new order admission is closed") from exc
        if ready is not True or not isinstance(evidence, dict) or evidence.get("admissible") is not True:
            raise AdmissionDenied("source or destination network is not ready; new order admission is closed")

    def register_quote(self, quote: OrderQuote, now: int | None = None) -> None:
        self._require_ready(quote.source_chain)
        self.ledger.register_quote(quote, now=now)

    def record_source_deposit(self, evidence: SourceDepositEvidence,
                              now: int | None = None) -> None:
        # Recheck immediately before accepting verified source-deposit evidence.
        self._require_ready(evidence.source_chain)
        self.ledger.record_source_deposit(evidence, now=now)

    def record_destination_payout(self, evidence: DestinationPayoutEvidence,
                                  now: int | None = None) -> None:
        """Allow completion/recovery of an existing order even while admission is paused."""
        self.ledger.record_destination_payout(evidence, now=now)
