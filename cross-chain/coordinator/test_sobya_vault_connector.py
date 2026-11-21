import unittest

from eth_hash.auto import keccak

from order_ledger import OrderQuote
from sobya_vault_connector import SobyaVaultReserver, VaultConnectorError


CHAIN_ID = 357812033857
VAULT = "0x" + "66" * 20
SOLVER = "0x" + "44" * 20
RECIPIENT = "0x" + "55" * 20
ORDER_ID = "0x" + "11" * 32
TX_HASH = "0x" + "aa" * 32
BLOCK_HASH = "0x" + "bb" * 32


def word(value):
    return int(value).to_bytes(32, "big").hex()


def address_word(value):
    return (bytes(12) + bytes.fromhex(value[2:])).hex()


class FakeRpc:
    def __init__(self, *, finalized=True):
        self.calls = []
        self.finalized = finalized
        self.reservation_reads = 0
        self.receipt = None

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "eth_chainId":
            return hex(CHAIN_ID)
        if method == "eth_getCode":
            return "0x60006000"
        if method == "eth_call":
            self.reservation_reads += 1
            if self.reservation_reads == 1:
                values = [0, 0, 0, 0, 0]
            else:
                values = [int(SOLVER, 16), int(RECIPIENT, 16), 123, 200, 1]
            return "0x" + "".join(word(value) for value in values)
        if method == "eth_getTransactionCount":
            return "0x0"
        if method == "eth_gasPrice":
            return "0x2"
        if method == "eth_estimateGas":
            return "0x5208"
        if method == "eth_sendRawTransaction":
            return TX_HASH
        if method == "eth_getTransactionReceipt":
            return self.receipt
        if method == "eth_getBlockByNumber":
            if params[0] == "finalized" and not self.finalized:
                return {"number": "0xf", "hash": BLOCK_HASH}
            return {"number": "0x20", "hash": BLOCK_HASH}
        if method == "eth_blockNumber":
            return "0x20"
        raise AssertionError(method)


def quote():
    return OrderQuote(
        order_id=ORDER_ID,
        source_chain="ethereum",
        source_asset="USDT",
        source_amount=1_000_000,
        user="0x" + "22" * 20,
        solver=SOLVER,
        destination_chain_id=CHAIN_ID,
        destination_recipient=RECIPIENT,
        destination_amount=123,
        quote_expiry=150,
        refund_after=200,
    )


class VaultConnectorTests(unittest.TestCase):
    def make_connector(self, rpc):
        return SobyaVaultReserver(
            rpc,
            expected_chain_id=CHAIN_ID,
            vault_address=VAULT,
            signer=lambda tx: "0x" + "deadbeef",
            confirmations=2,
        )

    def test_reserve_waits_for_finality_and_reads_exact_reservation(self):
        rpc = FakeRpc()
        event = "0x" + keccak(
            b"InventoryReserved(bytes32,address,address,uint256,uint64)"
        ).hex()
        rpc.receipt = {
            "transactionHash": TX_HASH,
            "to": VAULT,
            "status": "0x1",
            "blockNumber": "0x10",
            "blockHash": BLOCK_HASH,
            "logs": [{
                "address": VAULT,
                "topics": [
                    event,
                    ORDER_ID,
                    "0x" + address_word(SOLVER),
                    "0x" + address_word(RECIPIENT),
                ],
                "data": "0x" + word(123) + word(200),
            }],
        }
        connector = self.make_connector(rpc)
        self.assertIs(connector.reserve(quote()), True)
        methods = [method for method, _ in rpc.calls]
        self.assertIn("eth_sendRawTransaction", methods)
        self.assertEqual(methods.count("eth_call"), 2)

    def test_does_not_accept_unfinalized_reservation(self):
        rpc = FakeRpc(finalized=False)
        event = "0x" + keccak(
            b"InventoryReserved(bytes32,address,address,uint256,uint64)"
        ).hex()
        rpc.receipt = {
            "transactionHash": TX_HASH,
            "to": VAULT,
            "status": "0x1",
            "blockNumber": "0x10",
            "blockHash": BLOCK_HASH,
            "logs": [{
                "address": VAULT,
                "topics": [
                    event,
                    ORDER_ID,
                    "0x" + address_word(SOLVER),
                    "0x" + address_word(RECIPIENT),
                ],
                "data": "0x" + word(123) + word(200),
            }],
        }
        with self.assertRaises(VaultConnectorError):
            self.make_connector(rpc).reserve(quote())

    def test_rejects_chain_identity_mismatch(self):
        rpc = FakeRpc()
        rpc.call = lambda method, params: "0x1" if method == "eth_chainId" else None
        with self.assertRaises(VaultConnectorError):
            self.make_connector(rpc).reserve(quote())


if __name__ == "__main__":
    unittest.main()
