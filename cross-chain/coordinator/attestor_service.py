"""Local attestor service for independently verified cross-chain evidence.

This module signs only after the configured source/destination observer has
returned literal True and the finalized SOBYA vault reservation is read back.
It never accepts caller-supplied typed data, broadcasts transactions, or
submits escrow claims. EVM signatures are EIP-712; Solana payout approval is
returned as instruction data for a separately signed transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from attestation_payload import EvmPayoutAttestation, eip712_payout_digest
from eip712_quote_verifier import _recover_address
from order_ledger import (
    DestinationPayoutEvidence, OrderQuote, SourceDepositEvidence,
)
from source_deposit_attestation import (
    SourceDepositAttestation, eip712_source_deposit_digest,
)
from attestation_payload import build_solana_attest_payout_instruction


class AttestorServiceError(RuntimeError):
    """Raised when evidence or local signing policy cannot be established."""


@dataclass(frozen=True)
class PinnedSourceIdentity:
    """Canonical source identifiers expected by SOBYA settlement and source escrow."""
    source_chain: str
    source_chain_id: int
    source_chain_hash: str
    source_escrow_id: str
    source_asset_id: str
    source_escrow_address: str | None = None


@dataclass(frozen=True)
class FinalizedReservation:
    solver: str
    recipient: str
    amount: int
    release_after: int
    active: bool


class EvmSigningBackend:
    """Narrow adapter around a local wallet/HSM; implementation owns key custody."""

    def __init__(self, address: str, sign_digest: Callable[[bytes], bytes]):
        if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
            raise ValueError("attestor address must be a 20-byte EVM address")
        try:
            raw = bytes.fromhex(address[2:])
        except ValueError as exc:
            raise ValueError("attestor address is invalid hex") from exc
        if len(raw) != 20 or raw == bytes(20) or not callable(sign_digest):
            raise ValueError("attestor address or signing callback is invalid")
        self.address = "0x" + raw.hex()
        self._sign_digest = sign_digest

    def sign(self, digest: bytes) -> bytes:
        if not isinstance(digest, bytes) or len(digest) != 32:
            raise AttestorServiceError("EVM signer accepts only a 32-byte digest")
        signature = self._sign_digest(digest)
        if not isinstance(signature, bytes) or len(signature) != 65:
            raise AttestorServiceError("EVM signing backend must return a 65-byte signature")
        # Normalize v to the strict Solidity convention and verify key ownership.
        signature = signature[:64] + bytes([signature[64] + 27 if signature[64] in (0, 1) else signature[64]])
        if _recover_address(digest, signature).lower() != self.address.lower():
            raise AttestorServiceError("signature does not recover the configured attestor address")
        return signature


class LocalEvmKeyBackend(EvmSigningBackend):
    """In-memory secp256k1 signer; load its key from the encrypted local keystore."""

    def __init__(self, private_key: bytes):
        try:
            from eth_keys import keys
            key = keys.PrivateKey(private_key)
        except Exception as exc:
            raise ValueError("local attestor private key is invalid") from exc
        super().__init__(
            key.public_key.to_checksum_address(),
            lambda digest: key.sign_msg_hash(digest).to_bytes(),
        )


class AttestorService:
    """Evidence-gated signing for SOBYA release and source-escrow payout claims."""

    def __init__(
        self,
        *,
        attestor: EvmSigningBackend,
        quote_lookup: Callable[[str], OrderQuote],
        verify_source_deposit: Callable[[SourceDepositEvidence, Any], bool],
        verify_destination_payout: Callable[[DestinationPayoutEvidence, Any], bool],
        finalized_reservation: Callable[[str], FinalizedReservation],
        attestor_membership: Callable[[str, str, str], bool],
        settlement_contract: str,
        destination_chain_id: int,
        source_identities: dict[str, PinnedSourceIdentity],
    ):
        if not isinstance(attestor, EvmSigningBackend):
            raise ValueError("a local EVM signing backend is required")
        if not callable(quote_lookup) or not callable(verify_source_deposit):
            raise ValueError("quote lookup and source observer are mandatory")
        if (not callable(verify_destination_payout) or not callable(finalized_reservation)
                or not callable(attestor_membership)):
            raise ValueError("destination observer, finalized vault reader, and on-chain attestor membership reader are mandatory")
        if not isinstance(settlement_contract, str) or len(settlement_contract) != 42:
            raise ValueError("pinned SOBYA settlement contract is required")
        if destination_chain_id <= 0:
            raise ValueError("pinned SOBYA chain ID must be positive")
        self.attestor = attestor
        self.quote_lookup = quote_lookup
        self.verify_source_deposit = verify_source_deposit
        self.verify_destination_payout = verify_destination_payout
        self.finalized_reservation = finalized_reservation
        self.attestor_membership = attestor_membership
        self.settlement_contract = settlement_contract
        self.destination_chain_id = destination_chain_id
        self.source_identities = {k.lower(): v for k, v in source_identities.items()}

    def _quote(self, order_id: str) -> OrderQuote:
        quote = self.quote_lookup(order_id)
        if not isinstance(quote, OrderQuote) or quote.order_id.lower() != order_id.lower():
            raise AttestorServiceError("immutable registered quote is unavailable")
        return quote

    @staticmethod
    def _require_verified(callback: Callable[..., Any], *args: Any) -> None:
        try:
            result = callback(*args)
        except Exception as exc:
            raise AttestorServiceError("independent chain verification failed") from exc
        if result is not True:
            raise AttestorServiceError("chain evidence was not positively verified")

    def _identity(self, quote: OrderQuote) -> PinnedSourceIdentity:
        identity = self.source_identities.get(quote.source_chain.lower())
        if identity is None or identity.source_chain.lower() != quote.source_chain.lower():
            raise AttestorServiceError("source chain deployment identity is not pinned")
        return identity

    def _require_attestor_membership(self, network: str, contract: str) -> None:
        try:
            approved = self.attestor_membership(network, contract, self.attestor.address)
        except Exception as exc:
            raise AttestorServiceError("finalized on-chain attestor membership lookup failed") from exc
        if approved is not True:
            raise AttestorServiceError("configured attestor key is not active in the pinned on-chain contract")

    def _reservation(self, quote: OrderQuote) -> FinalizedReservation:
        try:
            reservation = self.finalized_reservation(quote.order_id)
        except Exception as exc:
            raise AttestorServiceError("finalized SOBYA vault reservation read failed") from exc
        if not isinstance(reservation, FinalizedReservation) or not reservation.active:
            raise AttestorServiceError("order has no active finalized SOBYA vault reservation")
        if (
            reservation.solver.lower() != quote.solver.lower()
            or reservation.recipient.lower() != quote.destination_recipient.lower()
            or reservation.amount != quote.destination_amount
            or reservation.release_after != quote.refund_after
        ):
            raise AttestorServiceError("finalized vault reservation does not match the immutable quote")
        return reservation

    def sign_source_deposit(
        self, evidence: SourceDepositEvidence, proof: Any
    ) -> dict[str, str]:
        """Authorize release of reserved SOBY only after source escrow finality."""
        if not isinstance(evidence, SourceDepositEvidence):
            raise AttestorServiceError("typed source deposit evidence is required")
        quote = self._quote(evidence.order_id)
        self._require_verified(self.verify_source_deposit, evidence, proof)
        self._reservation(quote)
        self._require_attestor_membership("sobya", self.settlement_contract)
        identity = self._identity(quote)
        if (
            evidence.source_chain.lower() != quote.source_chain.lower()
            or evidence.source_asset.lower() != quote.source_asset.lower()
            or evidence.source_amount != quote.source_amount
            or evidence.user.lower() != quote.user.lower()
            or evidence.solver.lower() != quote.solver.lower()
            or evidence.destination_chain_id != self.destination_chain_id
            or quote.destination_chain_id != self.destination_chain_id
            or evidence.destination_recipient.lower() != quote.destination_recipient.lower()
            or evidence.destination_amount != quote.destination_amount
        ):
            raise AttestorServiceError("source evidence differs from the immutable quote")
        payload = SourceDepositAttestation(
            order_id=quote.order_id,
            source_chain=identity.source_chain_hash,
            source_escrow=identity.source_escrow_id,
            source_asset=identity.source_asset_id,
            source_amount=quote.source_amount,
            recipient=quote.destination_recipient,
            soby_amount=quote.destination_amount,
            solver=quote.solver,
            destination_chain_id=self.destination_chain_id,
            release_after=quote.refund_after,
        )
        digest = eip712_source_deposit_digest(
            payload, settlement_contract=self.settlement_contract
        )
        signature = self.attestor.sign(digest)
        return {
            "order_id": quote.order_id,
            "digest": "0x" + digest.hex(),
            "attestor": self.attestor.address,
            "signature": "0x" + signature.hex(),
            "purpose": "SOBYA_SOURCE_DEPOSIT_RELEASE",
        }

    def sign_evm_source_payout(
        self, evidence: DestinationPayoutEvidence, proof: Any
    ) -> dict[str, str]:
        """Authorize solver claim of escrowed USDT after finalized SOBYA payout."""
        if not isinstance(evidence, DestinationPayoutEvidence):
            raise AttestorServiceError("typed destination payout evidence is required")
        quote = self._quote(evidence.order_id)
        self._require_verified(self.verify_destination_payout, evidence, proof)
        identity = self._identity(quote)
        if identity.source_escrow_address is None:
            raise AttestorServiceError("source escrow EVM/TVM address is not pinned")
        self._require_attestor_membership(quote.source_chain.lower(), identity.source_escrow_address)
        if (
            evidence.source_chain.lower() != quote.source_chain.lower()
            or evidence.source_asset.lower() != quote.source_asset.lower()
            or evidence.source_amount != quote.source_amount
            or evidence.recipient.lower() != quote.destination_recipient.lower()
            or evidence.destination_amount != quote.destination_amount
            or evidence.solver.lower() != quote.solver.lower()
            or evidence.destination_chain_id != self.destination_chain_id
        ):
            raise AttestorServiceError("finalized SOBYA payout differs from the immutable quote")
        if quote.source_chain.lower() == "solana":
            raise AttestorServiceError("Solana requires a signed AttestPayout transaction, not EIP-712")
        payload = EvmPayoutAttestation(
            order_id=quote.order_id,
            destination_tx_hash=evidence.transaction_id,
            destination_chain_id=self.destination_chain_id,
            destination_recipient=quote.destination_recipient,
            destination_amount=quote.destination_amount,
            source_escrow=identity.source_escrow_address,
            source_chain_id=identity.source_chain_id,
        )
        digest_hex = eip712_payout_digest(payload)
        digest = bytes.fromhex(digest_hex[2:])
        signature = self.attestor.sign(digest)
        return {
            "order_id": quote.order_id,
            "digest": digest_hex,
            "attestor": self.attestor.address,
            "signature": "0x" + signature.hex(),
            "purpose": "SOURCE_ESCROW_SOLVER_PAYOUT",
        }

    def build_solana_payout_instruction(
        self, evidence: DestinationPayoutEvidence, proof: Any
    ) -> dict[str, str]:
        """Return verified Solana AttestPayout instruction bytes; never broadcasts."""
        if not isinstance(evidence, DestinationPayoutEvidence):
            raise AttestorServiceError("typed destination payout evidence is required")
        quote = self._quote(evidence.order_id)
        if quote.source_chain.lower() != "solana":
            raise AttestorServiceError("order is not a Solana source escrow")
        self._require_verified(self.verify_destination_payout, evidence, proof)
        if (
            evidence.destination_chain_id != self.destination_chain_id
            or evidence.destination_amount != quote.destination_amount
            or evidence.recipient.lower() != quote.destination_recipient.lower()
            or evidence.solver.lower() != quote.solver.lower()
        ):
            raise AttestorServiceError("finalized SOBYA payout differs from the immutable quote")
        instruction = build_solana_attest_payout_instruction(
            quote.order_id, evidence.transaction_id
        )
        return {
            "order_id": quote.order_id,
            "instruction_data": "0x" + instruction.hex(),
            "attestor": self.attestor.address,
            "purpose": "SOLANA_ATTEST_PAYOUT_UNSIGNED_TRANSACTION",
        }
