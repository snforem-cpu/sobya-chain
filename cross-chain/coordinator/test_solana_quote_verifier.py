import unittest
from dataclasses import replace

from nacl.signing import SigningKey

from eip712_quote_verifier import Eip712QuoteDomain, Eip712QuoteVerifier
from order_ledger import OrderQuote
from quote_signature_router import ChainQuoteSignatureVerifier
from solana_quote_verifier import SolanaQuoteVerificationError, SolanaQuoteVerifier
from solana_source_observer import _b58encode


class SolanaQuoteVerifierTests(unittest.TestCase):
    def setUp(self):
        self.signing_key = SigningKey(bytes(range(32)))
        self.solver = _b58encode(bytes(self.signing_key.verify_key))
        self.user = _b58encode(bytes([21]) * 32)
        self.mint = _b58encode(bytes([22]) * 32)
        self.program_id = _b58encode(bytes([23]) * 32)
        self.authority = _b58encode(bytes([24]) * 32)
        self.quote = OrderQuote(
            order_id="0x" + "01" * 32,
            source_chain="solana",
            source_asset=self.mint,
            source_amount=25_000_000,
            user=self.user,
            solver=self.solver,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55" * 20,
            destination_amount=10**18,
            quote_expiry=1_900_000_000,
            refund_after=1_900_003_600,
        )
        self.verifier = SolanaQuoteVerifier(
            program_id=self.program_id,
            config_authority=self.authority,
            usdt_mint=self.mint,
            destination_chain_id=357812033857,
        )
        self.signature = self.signing_key.sign(self.verifier.message(self.quote)).signature

    def test_valid_ed25519_solver_quote(self):
        self.assertIs(self.verifier.verify(self.quote, self.signature), True)

    def test_quote_tampering_is_rejected(self):
        changed = replace(self.quote, destination_amount=2 * 10**18)
        with self.assertRaisesRegex(SolanaQuoteVerificationError, "signature is invalid"):
            self.verifier.verify(changed, self.signature)

    def test_wrong_mint_and_destination_chain_are_rejected(self):
        with self.assertRaisesRegex(SolanaQuoteVerificationError, "pinned Solana USDT mint"):
            self.verifier.message(replace(self.quote, source_asset=self.user))
        with self.assertRaisesRegex(SolanaQuoteVerificationError, "different SOBYA chain ID"):
            self.verifier.message(replace(self.quote, destination_chain_id=1))

    def test_signature_router_uses_native_solana_verifier(self):
        evm = Eip712QuoteVerifier({
            "ethereum": Eip712QuoteDomain(1, "0x" + "11" * 20),
        })
        router = ChainQuoteSignatureVerifier(evm, self.verifier)
        self.assertIs(router.verify(self.quote, self.signature), True)

    def test_router_fails_closed_when_solana_is_not_configured(self):
        evm = Eip712QuoteVerifier({
            "ethereum": Eip712QuoteDomain(1, "0x" + "11" * 20),
        })
        router = ChainQuoteSignatureVerifier(evm)
        with self.assertRaisesRegex(SolanaQuoteVerificationError, "not configured"):
            router.verify(self.quote, self.signature)

    def test_non_solana_quote_is_not_accepted_by_solana_verifier(self):
        changed = replace(self.quote, source_chain="ethereum")
        with self.assertRaisesRegex(SolanaQuoteVerificationError, "not a Solana"):
            self.verifier.message(changed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
