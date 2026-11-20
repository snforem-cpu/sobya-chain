"""Route quote signature verification to the source chain's native scheme."""
from __future__ import annotations

from typing import Any

from eip712_quote_verifier import Eip712QuoteVerifier
from order_ledger import OrderQuote
from solana_quote_verifier import SolanaQuoteVerifier, SolanaQuoteVerificationError


class ChainQuoteSignatureVerifier:
    def __init__(self, evm: Eip712QuoteVerifier,
                 solana: SolanaQuoteVerifier | None = None):
        self.evm = evm
        self.solana = solana

    def verify(self, quote: OrderQuote, signature: bytes) -> bool:
        if not isinstance(quote, OrderQuote):
            raise ValueError("a typed order quote is required")
        if quote.source_chain.lower() == "solana":
            if self.solana is None:
                raise SolanaQuoteVerificationError("Solana quote verification is not configured")
            return self.solana.verify(quote, signature)
        return self.evm.verify(quote, signature)
