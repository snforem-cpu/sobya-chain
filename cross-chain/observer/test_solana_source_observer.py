import base64
import unittest

from settlement_observer import VerificationError
from solana_source_observer import (
    ExpectedSolanaDeposit, SolanaDepositVerifier, SolanaRpc, LEGACY_SPL_TOKEN_PROGRAM,
    _find_program_address, _pubkey_bytes,
)

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58encode(raw):
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = ALPHABET[rem] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + (out or "")

def b58data(raw):
    return b58encode(raw)

def pk(byte):
    return b58encode(bytes([byte]) * 32)

def order_bytes(e):
    return b"".join([
        e.order_id, bytes([1])*32, bytes([2])*32, _pubkey_bytes(e.config_pda), bytes([6])*32,
        e.destination_recipient, e.destination_amount.to_bytes(16, "little"),
        e.source_amount.to_bytes(8, "little"), e.quote_expiry.to_bytes(8, "little"),
        e.refund_after.to_bytes(8, "little"), bytes(32), bytes(2), bytes([0, 254]),
    ])

class FakeSolana:
    def __init__(self, expected):
        self.e = expected
        self.order_data = order_bytes(expected)
        _, config_bump = _find_program_address(
            [b"config", _pubkey_bytes(expected.config_authority)], expected.program_id
        )
        config_data = (
            _pubkey_bytes(expected.config_authority) + bytes([config_bump])
            + _pubkey_bytes(expected.usdt_mint) + (357812033857).to_bytes(8, "little")
            + bytes([1]) + (1).to_bytes(4, "little") + _pubkey_bytes(pk(14))
        )
        self.config_data = base64.b64encode(config_data).decode()
        self.token_amount = str(expected.source_amount)
        self.tx = {
            "slot": 123,
            "transaction": {
                "signatures": [expected.signature],
                "message": {
                    "accountKeys": [
                        {"pubkey": expected.user, "signer": True},
                        {"pubkey": expected.solver, "signer": True},
                        {"pubkey": expected.config_pda, "signer": False},
                        {"pubkey": expected.order_pda, "signer": False},
                        {"pubkey": pk(5), "signer": False},
                        {"pubkey": expected.escrow_token_account, "signer": False},
                        {"pubkey": LEGACY_SPL_TOKEN_PROGRAM, "signer": False},
                        {"pubkey": pk(8), "signer": False},
                        {"pubkey": expected.program_id, "signer": False},
                    ],
                    "instructions": [{
                        "programIdIndex": 8, "accounts": list(range(8)),
                        "data": b58data(bytes([1]) + expected.order_id +
                            expected.destination_recipient +
                            expected.destination_amount.to_bytes(16, "little") +
                            expected.source_amount.to_bytes(8, "little") +
                            expected.quote_expiry.to_bytes(8, "little") +
                            expected.refund_after.to_bytes(8, "little")),
                    }],
                },
            },
            "meta": {"err": None},
        }

    def __call__(self, _url, payload, _timeout):
        method, params = payload["method"], payload["params"]
        if method == "getTransaction":
            result = self.tx
        elif method == "getAccountInfo" and params[0] == self.e.config_pda:
            result = {"value": {"owner": self.e.program_id,
                "data": [self.config_data, "base64"]}}
        elif method == "getAccountInfo" and params[0] == self.e.order_pda:
            result = {"value": {"owner": self.e.program_id,
                "data": [base64.b64encode(self.order_data).decode(), "base64"]}}
        elif method == "getAccountInfo" and params[0] == self.e.escrow_token_account:
            result = {"value": {"owner": LEGACY_SPL_TOKEN_PROGRAM, "data": {
                "parsed": {"info": {"mint": self.e.usdt_mint, "owner": self.e.order_pda,
                    "tokenAmount": {"amount": self.token_amount}}}}}}
        else:
            raise AssertionError(method)
        return {"jsonrpc": "2.0", "id": payload["id"], "result": result}

class SolanaSourceObserverTests(unittest.TestCase):
    def setUp(self):
        program_id, user, order_id = pk(9), pk(1), bytes([10]) * 32
        config_authority = pk(12)
        config_pda, _ = _find_program_address([b"config", _pubkey_bytes(config_authority)], program_id)
        order_pda, _ = _find_program_address([b"order", order_id], program_id)
        self.expected = ExpectedSolanaDeposit(
            signature="sig-test", program_id=program_id, order_pda=order_pda, config_pda=config_pda,
            config_authority=config_authority, sobya_chain_id=357812033857, user=user, solver=pk(2), escrow_token_account=pk(6), usdt_mint=pk(7),
            source_amount=25_000_000, order_id=order_id,
            destination_recipient=bytes([11])*20, destination_amount=10**18,
            quote_expiry=1_900_000_000, refund_after=1_900_003_600,
        )
        self.fake = FakeSolana(self.expected)
        self.verifier = SolanaDepositVerifier(
            SolanaRpc("https://solana.invalid", transport=self.fake))

    def test_valid_finalized_funding(self):
        got = self.verifier.verify(self.expected)
        self.assertEqual(got.slot, 123)
        self.assertEqual(got.source_amount, self.expected.source_amount)

    def test_forged_order_pda_rejected_before_rpc(self):
        from dataclasses import replace
        forged = replace(self.expected, order_pda=pk(4))
        with self.assertRaisesRegex(VerificationError, "order PDA does not match"):
            self.verifier.verify(forged)

    def test_forged_config_pda_rejected_before_rpc(self):
        from dataclasses import replace
        forged = replace(self.expected, config_pda=pk(3))
        with self.assertRaisesRegex(VerificationError, "config PDA does not match"):
            self.verifier.verify(forged)

    def test_missing_finalized_transaction_rejected(self):
        self.fake.tx = None
        with self.assertRaisesRegex(VerificationError, "not finalized"):
            self.verifier.verify(self.expected)

    def test_wrong_instruction_quote_rejected(self):
        self.fake.tx["transaction"]["message"]["instructions"][0]["data"] = b58data(b"bad")
        with self.assertRaisesRegex(VerificationError, "canonical Fund"):
            self.verifier.verify(self.expected)

    def test_wrong_order_state_rejected(self):
        self.fake.order_data = self.fake.order_data[:-2] + bytes([1]) + self.fake.order_data[-1:]
        with self.assertRaisesRegex(VerificationError, "status"):
            self.verifier.verify(self.expected)

    def test_wrong_mint_rejected(self):
        self.expected = self.expected
        self.fake.__call__ = lambda *args: None
        original = self.fake
        def transport(url, payload, timeout):
            result = original(url, payload, timeout)
            if payload["method"] == "getAccountInfo" and payload["params"][0] == self.expected.escrow_token_account:
                result["result"]["value"]["data"]["parsed"]["info"]["mint"] = pk(99)
            return result
        verifier = SolanaDepositVerifier(SolanaRpc("https://solana.invalid", transport=transport))
        with self.assertRaisesRegex(VerificationError, "mint or authority"):
            verifier.verify(self.expected)

if __name__ == "__main__":
    unittest.main(verbosity=2)
