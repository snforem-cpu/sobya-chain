import unittest

from solver_balance_reader import (
    BalanceVerificationError, FinalizedNativeBalanceReader,
)


class FakeRpc:
    url = "http://127.0.0.1:8545"

    def __init__(self, chain_id="0x534f425941", balance="0x1234"):
        self.chain_id = chain_id
        self.balance = balance
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return self.chain_id
        if method == "eth_getBalance":
            return self.balance
        raise AssertionError(method)


class FinalizedNativeBalanceReaderTests(unittest.TestCase):
    def test_reads_balance_at_finalized_tag_on_pinned_chain(self):
        rpc = FakeRpc()
        reader = FinalizedNativeBalanceReader(rpc, int("534f425941", 16))
        self.assertEqual(reader("0x" + "44" * 20), 0x1234)
        self.assertEqual(rpc.calls[-1], ("eth_getBalance", ["0x" + "44" * 20, "finalized"]))

    def test_rejects_wrong_chain(self):
        reader = FinalizedNativeBalanceReader(FakeRpc(chain_id="0x1"), int("534f425941", 16))
        with self.assertRaisesRegex(BalanceVerificationError, "chain ID mismatch"):
            reader("0x" + "44" * 20)

    def test_rejects_malformed_address(self):
        reader = FinalizedNativeBalanceReader(FakeRpc(), int("534f425941", 16))
        with self.assertRaisesRegex(BalanceVerificationError, "20-byte"):
            reader("0x1234")

    def test_rejects_malformed_balance(self):
        reader = FinalizedNativeBalanceReader(
            FakeRpc(balance="not-hex"), int("534f425941", 16)
        )
        with self.assertRaisesRegex(BalanceVerificationError, "balance query failed"):
            reader("0x" + "44" * 20)

    def test_rejects_public_rpc(self):
        rpc = FakeRpc()
        rpc.url = "https://public-rpc.example"
        with self.assertRaisesRegex(ValueError, "private self-hosted"):
            FinalizedNativeBalanceReader(rpc, int("534f425941", 16))


if __name__ == "__main__":
    unittest.main(verbosity=2)
