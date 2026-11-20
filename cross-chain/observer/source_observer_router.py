"""Chain-specific source deposit verification router.

This composes the existing Ethereum, TRON Solidity-Node, and Solana finalized
observers into the coordinator's strict evidence callback. RPC objects and
network identities are supplied from private self-hosted deployment config.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from settlement_observer import VerificationError
from ethereum_source_observer import EthereumDepositVerifier, ExpectedDeposit
from tron_source_observer import TronDepositVerifier, ExpectedTronDeposit
from solana_source_observer import (
    SolanaDepositVerifier, ExpectedSolanaDeposit, _find_program_address,
    _pubkey_bytes, _b58encode, LEGACY_SPL_TOKEN_PROGRAM,
)
from order_ledger import OrderQuote, SourceDepositEvidence


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


ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsJA8knL"


@dataclass(frozen=True)
class EthereumSourceConfig:
    chain_id: int
    escrow: str
    rpc: Any


@dataclass(frozen=True)
class TronSourceConfig:
    escrow: str
    genesis_hash: str
    rpc: Any


@dataclass(frozen=True)
class SolanaSourceConfig:
    program_id: str
    usdt_mint: str
    rpc: Any


def _associated_token_address(owner: str, mint: str) -> str:
    address, _ = _find_program_address(
        [_pubkey_bytes(owner), _pubkey_bytes(LEGACY_SPL_TOKEN_PROGRAM), _pubkey_bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM,
    )
    return address


class SourceObserverRouter:
    """Return True only when finalized on-chain evidence exactly matches the ledger evidence."""

    def __init__(
        self,
        *,
        quote_lookup: Callable[[str], OrderQuote],
        ethereum: dict[str, EthereumSourceConfig] | None = None,
        tron: dict[str, TronSourceConfig] | None = None,
        solana: SolanaSourceConfig | None = None,
    ):
        self.quote_lookup = quote_lookup
        self.ethereum = {k.lower(): v for k, v in (ethereum or {}).items()}
        self.tron = {k.lower(): v for k, v in (tron or {}).items()}
        self.solana = solana

    @staticmethod
    def _match_evidence(evidence: SourceDepositEvidence, expected: SourceDepositEvidence) -> bool:
        if evidence != expected:
            raise VerificationError("coordinator evidence does not exactly match finalized chain observation")
        return True

    def __call__(self, evidence: SourceDepositEvidence, proof: Any) -> bool:
        if not isinstance(evidence, SourceDepositEvidence) or not isinstance(proof, dict):
            raise VerificationError("source evidence and proof object are required")
        quote = self.quote_lookup(evidence.order_id)
        if not isinstance(quote, OrderQuote) or quote.order_id != evidence.order_id:
            raise VerificationError("registered quote is unavailable")
        if evidence.source_chain.lower() != quote.source_chain.lower():
            raise VerificationError("source chain does not match registered quote")

        chain = quote.source_chain.lower()
        if chain in self.ethereum:
            if set(proof) != {"transaction_id"} or not isinstance(proof["transaction_id"], str):
                raise VerificationError("Ethereum proof must contain only transaction_id")
            config = self.ethereum[chain]
            verifier = EthereumDepositVerifier(config.rpc, config.chain_id, config.escrow)
            expected = ExpectedDeposit(
                order_id=quote.order_id, user=quote.user, token=quote.source_asset,
                source_amount=quote.source_amount, solver=quote.solver,
                destination_chain_id=quote.destination_chain_id,
                destination_recipient=quote.destination_recipient,
                destination_amount=quote.destination_amount,
                quote_expiry=quote.quote_expiry, refund_after=quote.refund_after,
            )
            observed = verifier.verify(proof["transaction_id"], expected)
            actual = SourceDepositEvidence(
                order_id=quote.order_id, source_chain=chain,
                transaction_id=observed.transaction_hash, event_index=observed.log_index,
                source_asset=quote.source_asset, source_amount=quote.source_amount,
                user=quote.user, solver=quote.solver,
                destination_chain_id=observed.destination_chain_id,
                destination_recipient=quote.destination_recipient,
                destination_amount=quote.destination_amount,
                finalized_reference=f"ethereum:finalized:{observed.block_number}",
            )
            return self._match_evidence(evidence, actual)

        if chain in self.tron:
            if set(proof) != {"transaction_id"} or not isinstance(proof["transaction_id"], str):
                raise VerificationError("TRON proof must contain only transaction_id")
            config = self.tron[chain]
            verifier = TronDepositVerifier(config.rpc, config.escrow, config.genesis_hash)
            expected = ExpectedTronDeposit(
                order_id=quote.order_id, user=quote.user, token=quote.source_asset,
                source_amount=quote.source_amount, solver=quote.solver,
                destination_chain_id=quote.destination_chain_id,
                destination_recipient=quote.destination_recipient,
                destination_amount=quote.destination_amount,
                quote_expiry=quote.quote_expiry, refund_after=quote.refund_after,
            )
            observed = verifier.verify(proof["transaction_id"], expected)
            actual = SourceDepositEvidence(
                order_id=quote.order_id, source_chain=chain,
                transaction_id=observed.transaction_id, event_index=observed.log_index,
                source_asset=quote.source_asset, source_amount=quote.source_amount,
                user=quote.user, solver=quote.solver,
                destination_chain_id=observed.destination_chain_id,
                destination_recipient=quote.destination_recipient,
                destination_amount=quote.destination_amount,
                finalized_reference=f"tron:solidified:{observed.block_number}",
            )
            return self._match_evidence(evidence, actual)

        if chain == "solana" and self.solana is not None:
            if set(proof) != {"signature"} or not isinstance(proof["signature"], str):
                raise VerificationError("Solana proof must contain only transaction signature")
            config = self.solana
            order_id = bytes.fromhex(quote.order_id.removeprefix("0x"))
            recipient = bytes.fromhex(quote.destination_recipient.removeprefix("0x"))
            config_pda, _ = _find_program_address(
                [b"config", _pubkey_bytes(quote.user)], config.program_id
            )
            order_pda, _ = _find_program_address([b"order", order_id], config.program_id)
            escrow_token = _associated_token_address(order_pda, config.usdt_mint)
            expected = ExpectedSolanaDeposit(
                signature=proof["signature"], program_id=config.program_id,
                order_pda=order_pda, config_pda=config_pda,
                user=quote.user, solver=quote.solver,
                escrow_token_account=escrow_token, usdt_mint=config.usdt_mint,
                source_amount=quote.source_amount, order_id=order_id,
                destination_recipient=recipient,
                destination_amount=quote.destination_amount,
                quote_expiry=quote.quote_expiry, refund_after=quote.refund_after,
            )
            observed = SolanaDepositVerifier(config.rpc).verify(expected)
            actual = SourceDepositEvidence(
                order_id=quote.order_id, source_chain=chain,
                transaction_id=observed.signature, event_index=0,
                source_asset=quote.source_asset, source_amount=quote.source_amount,
                user=quote.user, solver=quote.solver,
                destination_chain_id=quote.destination_chain_id,
                destination_recipient=quote.destination_recipient,
                destination_amount=quote.destination_amount,
                finalized_reference=f"solana:finalized:{observed.slot}",
            )
            return self._match_evidence(evidence, actual)

        raise VerificationError("source chain has no enabled self-hosted observer configuration")
