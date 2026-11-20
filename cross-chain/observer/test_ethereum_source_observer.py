import unittest

from eth_hash.auto import keccak
from ethereum_source_observer import (
    ORDER_FUNDED_TOPIC, EthereumDepositVerifier, ExpectedDeposit,
)
from settlement_observer import JsonRpc, VerificationError


def word_int(value):
    return value.to_bytes(32, "big")


def word_address(value):
    return bytes(12) + bytes.fromhex(value[2:])


class FakeRpc:
    def __init__(self):
        self.chain_id = 1
        self.receipt = None
        self.transaction = None
        self.finalized_number = 120
        self.canonical_hash = "0x" + "bb" * 32
        self.token = "0x" + "33" * 20
        self.status = 1
        self.order = None

    def __call__(self, _url, payload, _timeout):
        method, params = payload["method"], payload["params"]
        if method == "eth_chainId":
            result = hex(self.chain_id)
        elif method == "eth_getTransactionReceipt":
            result = self.receipt
        elif method == "eth_getTransactionByHash":
            result = self.transaction
        elif method == "eth_getBlockByNumber":
            if params[0] == "finalized":
                result = {"number": hex(self.finalized_number)}
            else:
                result = {"hash": self.canonical_hash}
        elif method == "eth_call":
            data = params[0]["data"]
            if data.startswith("0xfc0c546a"):  # token()
                result = "0x" + word_address(self.token).hex()
            elif data.startswith("0x5b7b8f"):  # status(bytes32), selector checked below
                result = "0x" + word_int(self.status).hex()
            elif data.startswith("0x"):  # orders(bytes32), use selector map
                result = "0x" + b"".join(self.order).hex()
            else:
                raise AssertionError(data)
        else:
            raise AssertionError(method)
        return {"jsonrpc": "2.0", "id": payload["id"], "result": result}


class EthereumSourceObserverTests(unittest.TestCase):
    def setUp(self):
        self.escrow = "0x" + "11" * 20
        self.tx_hash = "0x" + "aa" * 32
        self.expected = ExpectedDeposit(
            order_id="0x" + "01" * 32,
            user="0x" + "22" * 20,
            token="0x" + "33" * 20,
            source_amount=25_000_000,
            solver="0x" + "44" * 20,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55" * 20,
            destination_amount=10**18,
            quote_expiry=1_900_000_000,
            refund_after=1_900_003_600,
        )
        self.fake = FakeRpc()
        self.rpc = JsonRpc("https://rpc.invalid", transport=self.fake)
        self.verifier = EthereumDepositVerifier(self.rpc, 1, self.escrow)
        self.fake.order = [
            bytes.fromhex(self.expected.order_id[2:]),
            word_address(self.expected.user), word_address(self.expected.token),
            word_int(self.expected.source_amount), word_address(self.expected.solver),
            word_int(self.expected.destination_chain_id),
            word_address(self.expected.destination_recipient),
            word_int(self.expected.destination_amount), word_int(self.expected.quote_expiry),
            word_int(self.expected.refund_after),
        ]
        self.fake.receipt = {
            "transactionHash": self.tx_hash, "to": self.escrow, "status": "0x1",
            "blockNumber": "0x64", "blockHash": self.fake.canonical_hash,
            "logs": [{
                "address": self.escrow,
                "topics": [
                    ORDER_FUNDED_TOPIC, self.expected.order_id,
                    "0x" + word_address(self.expected.user).hex(),
                    "0x" + word_address(self.expected.solver).hex(),
                ],
                "data": "0x" + word_int(self.expected.source_amount).hex(),
                "logIndex": "0x1",
            }],
        }
        self.fake.transaction = {
            "to": self.escrow, "from": self.expected.user, "value": "0x0",
        }

    def test_valid_finalized_source_deposit(self):
        result = self.verifier.verify(self.tx_hash, self.expected)
        self.assertEqual(result.amount, self.expected.source_amount)
        self.assertEqual(result.source_chain_id, 1)
        self.assertEqual(result.log_index, 1)

    def test_unfinalized_deposit_rejected(self):
        self.fake.finalized_number = 99
        with self.assertRaisesRegex(VerificationError, "not finalized"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_wrong_token_rejected(self):
        self.fake.token = "0x" + "66" * 20
        with self.assertRaisesRegex(VerificationError, "token"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_non_funded_order_rejected(self):
        self.fake.status = 2
        with self.assertRaisesRegex(VerificationError, "FUNDED"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_wrong_onchain_recipient_rejected(self):
        self.fake.order[6] = word_address("0x" + "77" * 20)
        with self.assertRaisesRegex(VerificationError, "destination_recipient"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_duplicate_funding_events_rejected(self):
        self.fake.receipt["logs"].append(dict(self.fake.receipt["logs"][0], logIndex="0x2"))
        with self.assertRaisesRegex(VerificationError, "exactly one"):
            self.verifier.verify(self.tx_hash, self.expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
