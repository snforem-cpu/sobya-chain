import unittest

from evm_deposit_watcher import (
    EvmDepositError, Erc20DepositVerifier, ExpectedErc20Deposit, TRANSFER_TOPIC,
)


TOKEN = "0x" + "11" * 20
INVENTORY = "0x" + "22" * 20
SENDER = "0x" + "33" * 20
TX = "0x" + "aa" * 32
BLOCK_HASH = "0x" + "bb" * 32
TOPIC_FROM = "0x" + "00" * 12 + "33" * 20
TOPIC_TO = "0x" + "00" * 12 + "22" * 20


class FakeRpc:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        value = self.responses[method]
        return value(*params) if callable(value) else value


def fixture(*, chain="0x1", status="0x1", finalized="0x64",
            amount="0x3e8", recipient=TOPIC_TO, sender=TOPIC_FROM):
    receipt = {
        "transactionHash": TX, "status": status, "blockNumber": "0x50",
        "blockHash": BLOCK_HASH,
        "logs": [{
            "address": TOKEN, "topics": [TRANSFER_TOPIC, sender, recipient],
            "data": amount, "logIndex": "0x2", "removed": False,
        }],
    }
    return {
        "eth_chainId": chain,
        "eth_getTransactionReceipt": receipt,
        "eth_getBlockByNumber": {"number": finalized},
    }


class Erc20DepositVerifierTests(unittest.TestCase):
    def setUp(self):
        self.expected = ExpectedErc20Deposit(
            chain_id=1, tx_hash=TX, token_contract=TOKEN,
            inventory_wallet=INVENTORY, sender_wallet=SENDER,
            amount_base_units=1000, log_index=2,
        )

    def test_accepts_exact_finalized_transfer(self):
        verified = Erc20DepositVerifier(FakeRpc(fixture())).verify(self.expected)
        self.assertEqual(verified.amount_base_units, 1000)
        self.assertEqual(verified.block_number, 80)
        self.assertEqual(verified.log_index, 2)

    def test_rejects_wrong_chain(self):
        with self.assertRaisesRegex(EvmDepositError, "chain ID"):
            Erc20DepositVerifier(FakeRpc(fixture(chain="0x2"))).verify(self.expected)

    def test_rejects_unfinalized_receipt(self):
        with self.assertRaisesRegex(EvmDepositError, "not finalized"):
            Erc20DepositVerifier(FakeRpc(fixture(finalized="0x40"))).verify(self.expected)

    def test_rejects_failed_transaction(self):
        with self.assertRaisesRegex(EvmDepositError, "did not succeed"):
            Erc20DepositVerifier(FakeRpc(fixture(status="0x0"))).verify(self.expected)

    def test_rejects_wrong_amount(self):
        with self.assertRaisesRegex(EvmDepositError, "Transfer log"):
            Erc20DepositVerifier(FakeRpc(fixture(amount="0x3e7"))).verify(self.expected)

    def test_rejects_wrong_recipient(self):
        wrong = "0x" + "00" * 12 + "44" * 20
        with self.assertRaisesRegex(EvmDepositError, "Transfer log"):
            Erc20DepositVerifier(FakeRpc(fixture(recipient=wrong))).verify(self.expected)

    def test_rejects_wrong_sender(self):
        wrong = "0x" + "00" * 12 + "44" * 20
        with self.assertRaisesRegex(EvmDepositError, "Transfer log"):
            Erc20DepositVerifier(FakeRpc(fixture(sender=wrong))).verify(self.expected)

    def test_rejects_missing_receipt(self):
        responses = fixture()
        responses["eth_getTransactionReceipt"] = None
        with self.assertRaisesRegex(EvmDepositError, "receipt missing"):
            Erc20DepositVerifier(FakeRpc(responses)).verify(self.expected)

    def test_requires_https_rpc(self):
        from evm_deposit_watcher import EvmRpc
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            EvmRpc("http://127.0.0.1:8545")


if __name__ == "__main__":
    unittest.main()
