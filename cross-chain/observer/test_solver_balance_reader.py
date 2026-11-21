import unittest

from eth_hash.auto import keccak
from solver_balance_reader import (
    BalanceVerificationError, FinalizedVaultInventoryReader,
)


CHAIN_ID = 357812033857
VAULT = "0x" + "77" * 20
SOLVER = "0x" + "44" * 20


class FakeRpc:
    url = "http://127.0.0.1:8545"

    def __init__(self, chain_id=None, available="0x1234", code="0x60006000"):
        self.chain_id = chain_id or hex(CHAIN_ID)
        self.available = available
        self.code = code
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return self.chain_id
        if method == "eth_getCode":
            return self.code
        if method == "eth_call":
            expected = "0x" + keccak(b"available(address)")[:4].hex()
            self.asserted = params[0]["data"].startswith(expected)
            return "0x" + int(self.available, 16).to_bytes(32, "big").hex()
        raise AssertionError(method)


class FinalizedVaultInventoryReaderTests(unittest.TestCase):
    def reader(self, rpc):
        return FinalizedVaultInventoryReader(rpc, CHAIN_ID, VAULT)

    def test_reads_available_vault_inventory_at_finalized_tag(self):
        rpc = FakeRpc()
        reader = self.reader(rpc)
        self.assertEqual(reader(SOLVER), 0x1234)
        self.assertEqual(rpc.calls[1], ("eth_getCode", [VAULT, "finalized"]))
        method, params = rpc.calls[2]
        self.assertEqual(method, "eth_call")
        self.assertEqual(params[1], "finalized")
        self.assertTrue(rpc.asserted)

    def test_rejects_wrong_chain(self):
        with self.assertRaisesRegex(BalanceVerificationError, "chain ID mismatch"):
            self.reader(FakeRpc(chain_id="0x1"))(SOLVER)

    def test_rejects_malformed_solver(self):
        with self.assertRaisesRegex(BalanceVerificationError, "20-byte"):
            self.reader(FakeRpc())("0x1234")

    def test_rejects_missing_vault_code(self):
        with self.assertRaisesRegex(BalanceVerificationError, "inventory query failed"):
            self.reader(FakeRpc(code="0x"))(SOLVER)

    def test_rejects_public_rpc(self):
        rpc = FakeRpc()
        rpc.url = "https://public-rpc.example"
        with self.assertRaisesRegex(ValueError, "private self-hosted"):
            self.reader(rpc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
