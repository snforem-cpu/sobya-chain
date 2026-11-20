import unittest
from eth_hash.auto import keccak
from settlement_observer import VerificationError
from tron_source_observer import ORDER_FUNDED_TOPIC, ExpectedTronDeposit, TronDepositVerifier, TronSolidityRpc

def wi(v): return v.to_bytes(32, "big")
def wa(v): return bytes(12) + bytes.fromhex(v[2:])

class FakeTron:
    def __init__(self, expected, escrow, txid):
        self.expected, self.escrow, self.txid = expected, escrow, txid
        self.token, self.status = expected.token, 1
        self.block_hash, self.genesis_hash = "ab" * 32, "ef" * 32
        self.order = [bytes.fromhex(expected.order_id[2:]), wa(expected.user), wa(expected.token),
            wi(expected.source_amount), wa(expected.solver), wi(expected.destination_chain_id),
            wa(expected.destination_recipient), wi(expected.destination_amount),
            wi(expected.quote_expiry), wi(expected.refund_after)]
        self.logs = [{"address": escrow[2:], "topics": [ORDER_FUNDED_TOPIC, expected.order_id,
            "0x" + wa(expected.user).hex(), "0x" + wa(expected.solver).hex()],
            "data": "0x" + wi(expected.source_amount).hex(), "logIndex": 2}]

    def __call__(self, url, payload, _timeout):
        if url.endswith("/walletsolidity/gettransactioninfobyid"):
            result = {"id": self.txid, "blockNumber": 90, "blockHash": self.block_hash,
                "receipt": {"result": "SUCCESS"}, "log": self.logs}
        elif url.endswith("/walletsolidity/gettransactionbyid"):
            result = {"txID": self.txid, "raw_data": {"contract": [{
                "type": "TriggerSmartContract", "parameter": {"value": {
                    "contract_address": "41" + self.escrow[2:],
                    "owner_address": "41" + self.expected.user[2:], "call_value": 0}}}]}}
        elif url.endswith("/walletsolidity/getblockbynum"):
            result = {"blockID": self.genesis_hash if payload["num"] == 0 else self.block_hash}
        elif url.endswith("/walletsolidity/triggerconstantcontract"):
            data = payload["data"]
            if data.startswith(keccak(b"token()")[:4].hex()): words = [wa(self.token)]
            elif data.startswith(keccak(b"status(bytes32)")[:4].hex()): words = [wi(self.status)]
            elif data.startswith(keccak(b"orders(bytes32)")[:4].hex()): words = self.order
            else: raise AssertionError(data)
            result = {"constant_result": ["".join(x.hex() for x in words)]}
        else: raise AssertionError(url)
        return result

class TronSourceObserverTests(unittest.TestCase):
    def setUp(self):
        self.escrow, self.txid = "0x" + "11"*20, "cd"*32
        self.expected = ExpectedTronDeposit("0x"+"01"*32, "0x"+"22"*20, "0x"+"33"*20,
            25_000_000, "0x"+"44"*20, 357812033857, "0x"+"55"*20, 10**18,
            1_900_000_000, 1_900_003_600)
        self.fake = FakeTron(self.expected, self.escrow, self.txid)
        self.verifier = TronDepositVerifier(
            TronSolidityRpc("https://tron.invalid", transport=self.fake),
            self.escrow, self.fake.genesis_hash)

    def test_valid_solidified_deposit(self):
        got = self.verifier.verify(self.txid, self.expected)
        self.assertEqual((got.amount, got.block_number, got.log_index), (25_000_000, 90, 2))

    def test_failed_transaction_rejected(self):
        original = self.fake
        def transport(url, payload, timeout):
            result = original(url, payload, timeout)
            if url.endswith("gettransactioninfobyid"): result["receipt"]["result"] = "REVERT"
            return result
        verifier = TronDepositVerifier(TronSolidityRpc("https://tron.invalid", transport=transport),
            self.escrow, self.fake.genesis_hash)
        with self.assertRaisesRegex(VerificationError, "failed"): verifier.verify(self.txid, self.expected)

    def test_missing_solidified_transaction_rejected(self):
        def transport(url, payload, timeout):
            result = self.fake(url, payload, timeout)
            return {} if url.endswith("gettransactioninfobyid") else result
        verifier = TronDepositVerifier(TronSolidityRpc("https://tron.invalid", transport=transport),
            self.escrow, self.fake.genesis_hash)
        with self.assertRaisesRegex(VerificationError, "not present in Solidity Node"):
            verifier.verify(self.txid, self.expected)

    def test_wrong_genesis_rejected(self):
        verifier = TronDepositVerifier(self.verifier.rpc, self.escrow, "00"*32)
        with self.assertRaisesRegex(VerificationError, "genesis hash"): verifier.verify(self.txid, self.expected)

    def test_wrong_token_rejected(self):
        self.fake.token = "0x" + "77"*20
        with self.assertRaisesRegex(VerificationError, "token"): self.verifier.verify(self.txid, self.expected)

    def test_duplicate_funding_logs_rejected(self):
        self.fake.logs.append(dict(self.fake.logs[0], logIndex=3))
        with self.assertRaisesRegex(VerificationError, "exactly one"): self.verifier.verify(self.txid, self.expected)

if __name__ == "__main__": unittest.main(verbosity=2)
