import tempfile
import unittest
from pathlib import Path

from eth_hash.auto import keccak
from settlement_observer import (
    EVENT_TOPIC, ExpectedPayout, JsonRpc, ObservationStore,
    SettlementVerifier, VerificationError,
)


def word_int(value):
    return value.to_bytes(32, "big")


def word_address(value):
    return bytes(12) + bytes.fromhex(value[2:])


class FakeRpc:
    def __init__(self, chain_id=357812033857, latest=120):
        self.chain_id = chain_id
        self.latest = latest
        self.finalized = 120
        self.receipt = None
        self.transaction = None
        self.block_hash = "0x" + "bb" * 32

    def __call__(self, _url, payload, _timeout):
        method = payload["method"]
        if method == "eth_chainId":
            result = hex(self.chain_id)
        elif method == "eth_blockNumber":
            result = hex(self.latest)
        elif method == "eth_getTransactionReceipt":
            result = self.receipt
        elif method == "eth_getTransactionByHash":
            result = self.transaction
        elif method == "eth_getBlockByNumber":
            if payload["params"][0] == "finalized":
                result = {"number": hex(self.finalized), "hash": self.block_hash}
            else:
                result = {"hash": self.block_hash}
        else:
            raise AssertionError(method)
        return {"jsonrpc": "2.0", "id": payload["id"], "result": result}


class SettlementObserverTests(unittest.TestCase):
    def setUp(self):
        self.contract = "0x" + "11" * 20
        self.tx_hash = "0x" + "aa" * 32
        self.expected = ExpectedPayout(
            order_id="0x" + "01" * 32,
            source_chain="0x" + keccak(b"ETHEREUM_MAINNET").hex(),
            source_escrow="0x" + "22" * 32,
            source_asset="0x" + "33" * 32,
            source_amount=25_000_000,
            recipient="0x" + "44" * 20,
            soby_amount=10**18,
            destination_solver="0x" + "55" * 20,
        )
        self.fake = FakeRpc()
        self.rpc = JsonRpc("https://rpc.invalid", transport=self.fake)
        self.verifier = SettlementVerifier(self.rpc, 357812033857, self.contract, 12)
        topics = [
            EVENT_TOPIC, self.expected.order_id, self.expected.source_chain,
            "0x" + word_address(self.expected.recipient).hex(),
        ]
        data = b"".join([
            bytes.fromhex(self.expected.source_escrow[2:]),
            bytes.fromhex(self.expected.source_asset[2:]),
            word_int(self.expected.source_amount), word_int(self.expected.soby_amount),
            word_address(self.expected.destination_solver), word_int(357812033857),
        ])
        self.fake.receipt = {
            "transactionHash": self.tx_hash, "to": self.contract,
            "status": "0x1", "blockNumber": "0x64", "blockHash": self.fake.block_hash,
            "logs": [{
                "address": self.contract, "topics": topics,
                "data": "0x" + data.hex(), "logIndex": "0x2",
            }],
        }
        self.fake.transaction = {
            "hash": self.tx_hash, "to": self.contract,
            "from": self.expected.destination_solver, "value": hex(self.expected.soby_amount),
        }

    def test_valid_finalized_payout_is_verified(self):
        result = self.verifier.verify(self.tx_hash, self.expected)
        self.assertEqual(result.order_id, self.expected.order_id)
        self.assertEqual(result.soby_amount, 10**18)
        self.assertEqual(result.log_index, 2)
        self.assertEqual(result.destination_chain_id, 357812033857)

    def test_wrong_destination_chain_rejected(self):
        self.fake.chain_id = 1
        with self.assertRaisesRegex(VerificationError, "chain ID mismatch"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_failed_transaction_rejected(self):
        self.fake.receipt["status"] = "0x0"
        with self.assertRaisesRegex(VerificationError, "transaction failed"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_wrong_contract_rejected(self):
        self.fake.receipt["to"] = "0x" + "99" * 20
        with self.assertRaisesRegex(VerificationError, "target"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_insufficient_confirmations_rejected(self):
        self.fake.latest = 110
        with self.assertRaisesRegex(VerificationError, "insufficient confirmations"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_unfinalized_payout_rejected_even_with_many_confirmations(self):
        self.fake.finalized = 99
        self.fake.latest = 120
        with self.assertRaisesRegex(VerificationError, "not finalized"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_missing_finalized_checkpoint_rejected(self):
        original = self.fake.__call__
        def without_finalized(url, payload, timeout):
            if payload["method"] == "eth_getBlockByNumber" and payload["params"][0] == "finalized":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": None}
            return original(url, payload, timeout)
        self.rpc.transport = without_finalized
        with self.assertRaisesRegex(VerificationError, "finalized checkpoint is unavailable"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_non_canonical_block_rejected(self):
        self.fake.block_hash = "0x" + "cc" * 32
        with self.assertRaisesRegex(VerificationError, "possible reorg"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_wrong_transaction_sender_rejected(self):
        self.fake.transaction["from"] = "0x" + "66" * 20
        with self.assertRaisesRegex(VerificationError, "does not match"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_wrong_transaction_value_rejected(self):
        self.fake.transaction["value"] = "0x1"
        with self.assertRaisesRegex(VerificationError, "does not match"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_wrong_amount_rejected(self):
        self.expected = ExpectedPayout(**{**self.expected.__dict__, "source_amount": 1})
        with self.assertRaisesRegex(VerificationError, "does not match"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_duplicate_matching_events_rejected(self):
        self.fake.receipt["logs"].append(dict(self.fake.receipt["logs"][0], logIndex="0x3"))
        with self.assertRaisesRegex(VerificationError, "exactly one"):
            self.verifier.verify(self.tx_hash, self.expected)

    def test_receipt_can_be_recorded_only_once(self):
        payout = self.verifier.verify(self.tx_hash, self.expected)
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationStore(str(Path(tmp) / "observations.sqlite"))
            store.record(payout)
            with self.assertRaisesRegex(VerificationError, "already recorded"):
                store.record(payout)
            store.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
