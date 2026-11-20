import unittest

from eth_hash.auto import keccak
from settlement_observer import VerificationError
from tron_source_observer import (
    ORDER_FUNDED_TOPIC, ExpectedTronDeposit, TronDepositVerifier, TronSolidityRpc,
)


def word_int(value):
    return value.to_bytes(32, "big")


def word_address(value):
    return bytes(12) + bytes.fromhex(value[2:])


class FakeTron:
    def __init__(self, expected, escrow, txid):
        self.expected, self.escrow, self.txid = expected, escrow, txid
        self.token = expected.token
        self.status = 1
        self.block_hash = "ab" * 32\n        self.genesis_hash = "ef" * 32
        self.order = [
            bytes.fromhex(expected.order_id[2:]), word_address(expected.user),
            word_address(expected.token), word_int(expected.source_amount),
            word_address(expected.solver), word_int(expected.destination_chain_id),
            word_address(expected.destination_recipient), word_int(expected.destination_amount),
            word_int(expected.quote_expiry), word_int(expected.refund_after),
        ]
        self.logs = [{
            "address": escrow[2:],
            "topics": [
                ORDER_FUNDED_TOPIC,
                expected.order_id,
                "0x" + word_address(expected.user).hex(),
                "0x" + word_address(expected.solver).hex(),
            ],
            "data": "0x" + word_int(expected.source_amount).hex(),
            "logIndex": 2,
        }]

    def __call__(self, url, payload, _timeout):
        if url.endswith("/walletsolidity/gettransactioninfobyid"):
            result = {
                "id": self.txid, "blockNumber": 90, "blockHash": self.block_hash,
                "receipt": {"result": "SUCCESS"}, "log": self.logs,
            }
        elif url.endswith("/walletsolidity/gettransactionbyid"):
            result = {"raw_data": {"contract": [{
                "type": "TriggerSmartContract",
                "parameter": {"value": {
                    "contract_address": "41" + self.escrow[2:],
                    "owner_address": "41" + self.expected.user[2:],
                    "call_value": 0,
                }},
            }]}}
        elif url.endswith("/walletsolidity/getblockbynum"):
            result = {"blockID": self.block_hash}
        elif url.endswith("/walletsolidity/triggerconstantcontract"):
            data = payload["data"]
            if data.startswith(keccak(b"token()")[:4].hex()):
                words = [word_address(self.token)]
            elif data.startswith(keccak(b"status(bytes32)")[:4].hex()):
                words = [word_int(self.status)]
            elif data.startswith(keccak(b"orders(bytes32)")[:4].hex()):
                words = self.order
            else:
                raise AssertionError(data)
            result = {"constant_result": ["".join(word.hex() for word in words)]}
        else:
            raise AssertionError(url)
        return result


class TronSourceObserverTests(unittest.TestCase):
    def setUp(self):
        self.escrow = "0x" + "11" * 20
        self.txid = "cd" * 32
        self.expected = ExpectedTronDeposit(
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
        self.fake = FakeTron(self.expected, self.escrow, self.txid)
        self.rpc = TronSolidityRpc("https://tron.invalid", transport=self.fake)
        self.verifier = TronDepositVerifier(self.rpc, self.escrow, self.fake.genesis_hash)

    def test_valid_solidified_deposit(self):
        result = self.verifier.verify(self.txid, self.expected)
        self.assertEqual(result.amount, self.expected.source_amount)
        self.assertEqual(result.block_number, 90)
        self.assertEqual(result.log_index, 2)

    def test_failed_transaction_rejected(self):
        original = self.fake
        def transport(url, payload, timeout):
            result = original(url, payload, timeout)
            if url.endswith("gettransactioninfobyid"):
                result["receipt"]["result"] = "REVERT"
            return result
        verifier = TronDepositVerifier(
            TronSolidityRpc("https://tron.invalid", transport=transport), self.escrow
        )
        with self.assertRaisesRegex(VerificationError, "failed"):
            verifier.verify(self.txid, self.expected)

    def test_unconfirmed_or_missing_solidity_node_transaction_rejected(self):
        def transport(url, payload, timeout):
            result = self.fake(url, payload, timeout)
            if url.endswith("gettransactioninfobyid"):
                return {}
            return result
        verifier = TronDepositVerifier(
            TronSolidityRpc("https://tron.invalid", transport=transport), self.escrow
        )
        with self.assertRaisesRegex(VerificationError, "not present in Solidity Node"):
            verifier.verify(self.txid, self.expected)

    def test_wrong_contract_rejected(self):
        self.fake.escrow = "0x" + "66" * 20
        with self.assertRaisesRegex(VerificationError, "target"):
            self.verifier.verify(self.txid, self.expected)

    def test_wrong_token_rejected(self):
        self.fake.token = "0x" + "77" * 20
        with self.assertRaisesRegex(VerificationError, "token"):
            self.verifier.verify(self.txid, self.expected)

    def test_duplicate_funding_logs_rejected(self):
        self.fake.logs.append(dict(self.fake.logs[0], logIndex=3))
        with self.assertRaisesRegex(VerificationError, "exactly one"):
            self.verifier.verify(self.txid, self.expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
