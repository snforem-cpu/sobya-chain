import unittest

from eth_hash.auto import keccak
from eip712_quote_verifier import (
    Eip712QuoteDomain, Eip712QuoteVerifier, N, G, HALF_N, _mul, _add,
    SignatureVerificationError,
)
from order_ledger import OrderQuote


def sign_digest(private_key: int, digest: bytes, nonce: int) -> bytes:
    point = _mul(nonce)
    r = point[0] % N
    s = (pow(nonce, N - 2, N) * (int.from_bytes(digest, "big") + r * private_key)) % N
    recovery = point[1] & 1
    if s > HALF_N:
        s = N - s
        recovery ^= 1
    return r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([27 + recovery])


class Eip712QuoteVerifierTests(unittest.TestCase):
    def setUp(self):
        self.private_key = 0x123456789ABCDEF
        public = _mul(self.private_key)
        self.solver = "0x" + keccak(
            public[0].to_bytes(32, "big") + public[1].to_bytes(32, "big")
        )[-20:].hex()
        self.quote = OrderQuote(
            order_id="0x" + "01"*32, source_chain="ethereum",
            source_asset="0x" + "33"*20, source_amount=20_000_000,
            user="0x" + "22"*20, solver=self.solver,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55"*20,
            destination_amount=10**18, quote_expiry=1_900_000_000,
            refund_after=1_900_003_600,
        )
        self.verifier = Eip712QuoteVerifier({
            "ethereum": Eip712QuoteDomain(1, "0x" + "11"*20),
        })

    def test_valid_solver_signature(self):
        digest = self.verifier.digest(self.quote)
        signature = sign_digest(self.private_key, digest, 0xABCDEF123456789)
        self.assertIs(self.verifier.verify(self.quote, signature), True)

    def test_wrong_solver_and_tampering_rejected(self):
        digest = self.verifier.digest(self.quote)
        signature = sign_digest(self.private_key, digest, 0xABCDEF123456789)
        changed = OrderQuote(**{**self.quote.__dict__, "destination_amount": 2 * 10**18})
        self.assertIs(self.verifier.verify(changed, signature), False)

    def test_bad_signature_rejected(self):
        with self.assertRaises(SignatureVerificationError):
            self.verifier.verify(self.quote, b"bad")

    def test_unconfigured_chain_rejected(self):
        changed = OrderQuote(**{**self.quote.__dict__, "source_chain": "solana"})
        with self.assertRaises(SignatureVerificationError):
            self.verifier.digest(changed)


if __name__ == "__main__":
    unittest.main()
