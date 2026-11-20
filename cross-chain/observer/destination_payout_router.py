"""Finalized SOBYA payout observer router for cross-chain orders."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from settlement_observer import SettlementVerifier, ExpectedPayout, VerificationError
from order_ledger import OrderQuote, DestinationPayoutEvidence
from self_hosted_supervisor import validate_self_hosted_url, SupervisorConfigError


def quote_from_ledger(ledger: Any, order_id: str) -> OrderQuote:
    """Adapt the immutable quote stored by CrossChainOrderLedger for observer checks."""
    record = ledger.get_order(order_id)
    quote = record.get("quote") if isinstance(record, dict) else None
    if not isinstance(quote, dict):
        raise VerificationError("registered quote record is malformed")
    try:
        return OrderQuote(**quote)
    except (TypeError, ValueError) as exc:
        raise VerificationError("registered quote record is malformed") from exc


@dataclass(frozen=True)
class SobyaSettlementConfig:
    destination_chain_id: int
    settlement_contract: str
    confirmations: int
    rpc: Any


@dataclass(frozen=True)
class SourceIdentity:
    # Canonical bytes32 values used by SobyaCrossChainSettlement.
    source_chain_id: str
    source_escrow_id: str
    source_asset_id: str


class DestinationPayoutRouter:
    """Verify the exact PayoutExecuted receipt on SOBYA before coordinator acceptance."""

    def __init__(
        self,
        *,
        quote_lookup: Callable[[str], OrderQuote],
        settlement: SobyaSettlementConfig,
        source_identities: dict[str, SourceIdentity],
    ):
        self.quote_lookup = quote_lookup
        self.settlement = settlement
        self.source_identities = {key.lower(): value for key, value in source_identities.items()}

    def __call__(self, evidence: DestinationPayoutEvidence, proof: Any) -> bool:
        if not isinstance(evidence, DestinationPayoutEvidence) or not isinstance(proof, dict):
            raise VerificationError("destination evidence and proof object are required")
        if set(proof) != {"transaction_hash"} or not isinstance(proof["transaction_hash"], str):
            raise VerificationError("SOBYA payout proof must contain only transaction_hash")
        quote = self.quote_lookup(evidence.order_id)
        if not isinstance(quote, OrderQuote):
            raise VerificationError("registered quote is unavailable")
        source = quote.source_chain.lower()
        identity = self.source_identities.get(source)
        if identity is None:
            raise VerificationError("source identity is not pinned for this network")
        if (
            evidence.source_chain.lower() != source
            or evidence.source_asset.lower() != quote.source_asset.lower()
            or evidence.source_amount != quote.source_amount
            or evidence.recipient.lower() != quote.destination_recipient.lower()
            or evidence.destination_amount != quote.destination_amount
            or evidence.solver.lower() != quote.solver.lower()
        ):
            raise VerificationError("payout evidence does not match registered quote")

        expected = ExpectedPayout(
            order_id=quote.order_id,
            source_chain=identity.source_chain_id,
            source_escrow=identity.source_escrow_id,
            source_asset=identity.source_asset_id,
            source_amount=quote.source_amount,
            recipient=quote.destination_recipient,
            soby_amount=quote.destination_amount,
            destination_solver=quote.solver,
        )
        rpc_url = getattr(self.settlement.rpc, "url", None)
        if not isinstance(rpc_url, str):
            raise VerificationError("SOBYA observer RPC must expose its configured URL")
        try:
            validate_self_hosted_url(rpc_url)
        except SupervisorConfigError as exc:
            raise VerificationError("SOBYA payout observer must use a private self-hosted node") from exc
        verifier = SettlementVerifier(
            self.settlement.rpc, self.settlement.destination_chain_id,
            self.settlement.settlement_contract, self.settlement.confirmations,
        )
        observed = verifier.verify(proof["transaction_hash"], expected)
        expected_evidence = DestinationPayoutEvidence(
            order_id=quote.order_id,
            transaction_id=observed.transaction_hash,
            event_index=observed.log_index,
            destination_chain_id=observed.destination_chain_id,
            source_chain=source,
            source_asset=quote.source_asset,
            source_amount=quote.source_amount,
            recipient=quote.destination_recipient,
            destination_amount=quote.destination_amount,
            solver=quote.solver,
            finalized_reference=f"sobya:confirmations:{observed.block_number}",
        )
        if evidence != expected_evidence:
            raise VerificationError("coordinator payout evidence differs from finalized SOBYA receipt")
        return True
