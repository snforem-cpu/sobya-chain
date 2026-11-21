"""Ed25519 verification for chain-native Solana solver quotes."""
from __future__ import annotations

import json
import re

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from order_ledger import OrderQuote
from solana_source_observer import _pubkey_bytes


class SolanaQuoteVerificationError(ValueError):
    pass


class SolanaQuoteVerifier:
    """Verify canonical Ed25519 quote signatures bound to one Solana escrow deployment."""

    DOMAIN = b"SOBYA_SOLANA_QUOTE_V1\x00"

    def __init__(self, *, program_id: str, config_authority: str,
                 usdt_mint: str, destination_chain_id: int):
        self.program_id = program_id
        self.config_authority = config_authority
        self.usdt_mint = usdt_mint
        self.destination_chain_id = destination_chain_id
        for value in (program_id, config_authority, usdt_mint):
            _pubkey_bytes(value)
        if not isinstance(destination_chain_id, int) or destination_chain_id <= 0:
            raise ValueError("destination chain ID must be positive")

    def message(self, quote: OrderQuote) -> bytes:
        if not isinstance(quote, OrderQuote) or quote.source_chain.lower() != "solana":
            raise SolanaQuoteVerificationError("quote is not a Solana source quote")
        if quote.destination_chain_id != self.destination_chain_id:
            raise SolanaQuoteVerificationError("quote targets a different SOBYA chain ID")
        if quote.source_asset != self.usdt_mint:
            raise SolanaQuoteVerificationError("quote source asset is not the pinned Solana USDT mint")
        try:
            _pubkey_bytes(quote.user)
            _pubkey_bytes(quote.solver)
            _pubkey_bytes(quote.source_asset)
            order_id = bytes.fromhex(quote.order_id.removeprefix("0x"))
            recipient = bytes.fromhex(quote.destination_recipient.removeprefix("0x"))
        except (TypeError, ValueError) as exc:
            raise SolanaQuoteVerificationError("quote contains an invalid Solana key or binary field") from exc
        if len(order_id) != 32 or len(recipient) != 20:
            raise SolanaQuoteVerificationError("order ID or SOBYA recipient has an invalid length")
        limits = (
            (quote.source_amount, 64), (quote.destination_amount, 128),
            (quote.quote_expiry, 64), (quote.refund_after, 64),
        )
        if any(not isinstance(value, int) or isinstance(value, bool)
               or value <= 0 or value >= 1 << bits for value, bits in limits):
            raise SolanaQuoteVerificationError("quote amount or deadline is outside the on-chain integer range")
        if quote.refund_after <= quote.quote_expiry:
            raise SolanaQuoteVerificationError("refund deadline must follow quote expiry")
        payload = {
            "domain": {
                "program_id": self.program_id,
                "config_authority": self.config_authority,
                "usdt_mint": self.usdt_mint,
                "destination_chain_id": self.destination_chain_id,
            },
            "quote": {
                "order_id": "0x" + order_id.hex(),
                "source_chain": "solana",
                "source_asset": quote.source_asset,
                "source_amount": quote.source_amount,
                "user": quote.user,
                "solver": quote.solver,
                "destination_chain_id": quote.destination_chain_id,
                "destination_recipient": "0x" + recipient.hex(),
                "destination_amount": quote.destination_amount,
                "quote_expiry": quote.quote_expiry,
                "refund_after": quote.refund_after,
            },
        }
        return self.DOMAIN + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")

    def verify(self, quote: OrderQuote, signature: bytes) -> bool:
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise SolanaQuoteVerificationError("Solana quote signature must be 64 bytes")
        message = self.message(quote)
        try:
            VerifyKey(_pubkey_bytes(quote.solver)).verify(message, signature)
        except (BadSignatureError, ValueError) as exc:
            raise SolanaQuoteVerificationError("Solana solver quote signature is invalid") from exc
        return True
