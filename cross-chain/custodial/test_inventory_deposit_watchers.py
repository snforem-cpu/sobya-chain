import unittest
import tempfile
from pathlib import Path
from inventory_deposit_watchers import (
    ExpectedInventoryDeposit, InventoryDepositError, EvmInventoryDepositVerifier,
    JsonRpc, SolanaInventoryDepositVerifier, TronInventoryDepositVerifier,
    TRANSFER_TOPIC, InventoryDepositRecorder, VerifiedInventoryDeposit,
)
from custodial_ledger import CustodialOrderLedger, CustodialOrderError

TOKEN = "0x" + "a1" * 20
INVENTORY = "0x" + "b2" * 20
SENDER = "0x" + "c3" * 20
TX = "0x" + "aa" * 32
BLOCK_HASH = "0x" + "bb" * 32
TOPIC_FROM = "0x" + "00" * 12 + "c3" * 20
TOPIC_TO = "0x" + "00" * 12 + "b2" * 20


class FakeRpc:
    def __init__(self, responses):
        self.responses = responses

    def call(self, method, params):
        result = self.responses[method]
        return result(*params) if callable(result) else result


def evm_fixture(chain="0x1", finalized="0x64", status="0x1", amount="0x3e8"):
    receipt = {
        "transactionHash": TX, "status": status, "blockNumber": "0x50",
        "blockHash": BLOCK_HASH,
        "logs": [{
            "address": TOKEN, "topics": [TRANSFER_TOPIC, TOPIC_FROM, TOPIC_TO],
            "data": amount, "logIndex": "0x2", "removed": False,
        }],
    }
    return {
        "eth_chainId": chain,
        "eth_getTransactionReceipt": receipt,
        "eth_getBlockByNumber": lambda tag, full: (
            {"number": finalized} if tag == "finalized"
            else {"number": tag, "hash": BLOCK_HASH}
        ),
    }


class EvmInventoryWatcherTests(unittest.TestCase):
    def setUp(self):
        self.expected = ExpectedInventoryDeposit(
            "ethereum", TX, SENDER, INVENTORY, TOKEN, 1000, 2
        )

    def test_exact_finalized_erc20_deposit(self):
        got = EvmInventoryDepositVerifier(JsonRpc(
            "https://rpc.invalid", transport=lambda *_: None
        ), 1)
        got.rpc = FakeRpc(evm_fixture())
        verified = got.verify(self.expected)
        self.assertEqual(verified.amount_base_units, 1000)
        self.assertEqual(verified.finalized_reference, "ethereum:finalized:80")

    def test_wrong_chain_rejected(self):
        verifier = EvmInventoryDepositVerifier(JsonRpc(
            "https://rpc.invalid", transport=lambda *_: None
        ), 1)
        verifier.rpc = FakeRpc(evm_fixture(chain="0x2"))
        with self.assertRaisesRegex(InventoryDepositError, "chain ID"):
            verifier.verify(self.expected)

    def test_unfinalized_rejected(self):
        verifier = EvmInventoryDepositVerifier(JsonRpc(
            "https://rpc.invalid", transport=lambda *_: None
        ), 1)
        verifier.rpc = FakeRpc(evm_fixture(finalized="0x40"))
        with self.assertRaisesRegex(InventoryDepositError, "not finalized"):
            verifier.verify(self.expected)

    def test_wrong_amount_rejected(self):
        verifier = EvmInventoryDepositVerifier(JsonRpc(
            "https://rpc.invalid", transport=lambda *_: None
        ), 1)
        verifier.rpc = FakeRpc(evm_fixture(amount="0x3e7"))
        with self.assertRaisesRegex(InventoryDepositError, "Transfer event"):
            verifier.verify(self.expected)

    def test_native_sobya_deposit(self):
        responses = {
            "eth_chainId": "0x" + format(357812033857, "x"),
            "eth_getTransactionReceipt": {
                "transactionHash": TX, "status": "0x1", "blockNumber": "0x50",
                "blockHash": BLOCK_HASH, "logs": [],
            },
            "eth_getBlockByNumber": lambda tag, full: (
                {"number": "0x64"} if tag == "finalized"
                else {"number": tag, "hash": BLOCK_HASH}
            ),
            "eth_getTransactionByHash": {
                "from": SENDER, "to": INVENTORY, "value": hex(123456),
            },
        }
        verifier = EvmInventoryDepositVerifier(JsonRpc(
            "https://rpc.invalid", transport=lambda *_: None
        ), 357812033857)
        verifier.rpc = FakeRpc(responses)
        expected = ExpectedInventoryDeposit(
            "sobya", TX, SENDER, INVENTORY, "asobya", 123456, 0
        )
        self.assertEqual(verifier.verify(expected).amount_base_units, 123456)

    def test_native_wrong_recipient_rejected(self):
        responses = {
            "eth_chainId": "0x" + format(357812033857, "x"),
            "eth_getTransactionReceipt": {
                "transactionHash": TX, "status": "0x1", "blockNumber": "0x50",
                "blockHash": BLOCK_HASH, "logs": [],
            },
            "eth_getBlockByNumber": lambda tag, full: (
                {"number": "0x64"} if tag == "finalized"
                else {"number": tag, "hash": BLOCK_HASH}
            ),
            "eth_getTransactionByHash": {
                "from": SENDER, "to": SENDER, "value": hex(123456),
            },
        }
        verifier = EvmInventoryDepositVerifier(JsonRpc(
            "https://rpc.invalid", transport=lambda *_: None
        ), 357812033857)
        verifier.rpc = FakeRpc(responses)
        expected = ExpectedInventoryDeposit(
            "sobya", TX, SENDER, INVENTORY, "asobya", 123456, 0
        )
        with self.assertRaisesRegex(InventoryDepositError, "recipient mismatch"):
            verifier.verify(expected)


class TronInventoryWatcherTests(unittest.TestCase):
    def test_trc20_transfer_from_solidified_node(self):
        # Well-known, checksum-valid TRON test-format addresses are not needed:
        # use the project inventory and sender Base58 forms in fixture as constants.
        sender = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
        inventory = "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx"
        token = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
        # Convert Base58Check addresses to 21-byte hex using the module normalizer.
        from inventory_deposit_watchers import _tron_hex_address
        from_hex = _tron_hex_address(sender, "sender")[2:]
        to_hex = _tron_hex_address(inventory, "inventory")[2:]
        token_hex = _tron_hex_address(token, "token")
        txid = "ab" * 32
        def transport(url, payload, timeout):
            if url.endswith("/walletsolidity/gettransactioninfobyid"):
                return {
                    "id": txid, "blockNumber": 500,
                    "receipt": {"result": "SUCCESS"},
                    "log": [{
                        "address": token_hex,
                        "topics": [TRANSFER_TOPIC[2:], "0" * 24 + from_hex[-40:],
                                   "0" * 24 + to_hex[-40:]],
                        "data": hex(1000)[2:],
                    }],
                }
            return {"blockID": "cd" * 32}
        verifier = TronInventoryDepositVerifier("https://tron-solidity.invalid", transport=transport)
        expected = ExpectedInventoryDeposit(
            "tron", txid, sender, inventory, token, 1000, 0
        )
        self.assertEqual(verifier.verify(expected).amount_base_units, 1000)

    def test_tron_requires_solidified_success(self):
        txid = "ab" * 32
        def transport(url, payload, timeout):
            return {"id": txid, "blockNumber": 500, "receipt": {"result": "FAILED"}, "log": []}
        verifier = TronInventoryDepositVerifier("https://tron-solidity.invalid", transport=transport)
        expected = ExpectedInventoryDeposit(
            "tron", txid, "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx",
            "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj", 1000, 0
        )
        with self.assertRaisesRegex(InventoryDepositError, "did not succeed"):
            verifier.verify(expected)


class SolanaInventoryWatcherTests(unittest.TestCase):
    def test_finalized_spl_transfer_to_inventory_owner(self):
        sender = "SenderPublicKey111111111111111111111111111111"
        inventory = "InventoryPublicKey11111111111111111111111111"
        mint = "UsdtMintPublicKey111111111111111111111111111"
        token_program = "TokenProgram11111111111111111111111111111"
        source_ata = "SourceTokenAccount11111111111111111111111111"
        destination_ata = "InventoryTokenAccount1111111111111111111111"
        signature = "signature"
        tx = {
            "slot": 999, "meta": {"err": None},
            "transaction": {"message": {"accountKeys": [token_program], "instructions": [{
                "programIdIndex": 0, "parsed": {"type": "transferChecked", "info": {
                    "authority": sender, "source": source_ata, "destination": destination_ata,
                    "mint": mint, "tokenAmount": {"amount": "1000"},
                }},
            }]}, "signatures": [signature]},
        }
        def call(method, params):
            if method == "getTransaction":
                return tx
            if method == "getAccountInfo" and params[0] == destination_ata:
                return {"value": {"owner": token_program, "data": {"parsed": {"info": {
                    "mint": mint, "owner": inventory,
                }}}}}
            raise AssertionError(method)
        verifier = SolanaInventoryDepositVerifier(JsonRpc(
            "https://solana-rpc.invalid", transport=lambda *_: None
        ), token_program)
        verifier.rpc = FakeRpc({"getTransaction": lambda *_: tx,
            "getAccountInfo": lambda address, config: {
                "value": {"owner": token_program, "data": {"parsed": {"info": {
                    "mint": mint, "owner": inventory,
                }}}}
            }})
        expected = ExpectedInventoryDeposit(
            "solana", signature, sender, inventory, mint, 1000, 0
        )
        self.assertEqual(verifier.verify(expected).finalized_reference, "solana:finalized:999")

    def test_failed_solana_transaction_rejected(self):
        verifier = SolanaInventoryDepositVerifier(JsonRpc(
            "https://solana-rpc.invalid", transport=lambda *_: None
        ), "TokenProgram11111111111111111111111111111")
        verifier.rpc = FakeRpc({"getTransaction": {
            "slot": 999, "meta": {"err": {"InstructionError": [0, "Custom"]}},
            "transaction": {"message": {"accountKeys": [], "instructions": []}},
        }})
        expected = ExpectedInventoryDeposit(
            "solana", "signature", "Sender11111111111111111111111111111111",
            "Inventory1111111111111111111111111111",
            "Mint111111111111111111111111111111111", 1000, 0
        )
        with self.assertRaisesRegex(InventoryDepositError, "failed"):
            verifier.verify(expected)


class InventoryDepositRecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = CustodialOrderLedger(Path(self.temp.name) / "orders.sqlite")
        self.order = self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum",
            destination_network="sobya", deposit_address=INVENTORY,
            source_wallet=SENDER, destination_wallet="0x" + "dd" * 20,
            source_asset=TOKEN, destination_asset="SOBY",
            source_amount=1000, destination_amount=2000,
        )
        self.expected = ExpectedInventoryDeposit(
            "ethereum", TX, SENDER, INVENTORY, TOKEN, 1000, 2
        )
        self.verified = VerifiedInventoryDeposit(
            "ethereum", TX, SENDER, INVENTORY, TOKEN, 1000, 2,
            "ethereum:finalized:80",
        )

    def test_verified_event_is_credited_and_retry_is_idempotent(self):
        class Verifier:
            def verify(inner, expected):
                return self.verified
        recorder = InventoryDepositRecorder(self.ledger)
        recorder.verify_and_record(Verifier(), self.order, self.expected)
        self.assertEqual(self.ledger.get_order(self.order)["state"], "deposit_final")
        # Simulate a worker restart after DB commit but before HTTP response.
        recorder.verify_and_record(Verifier(), self.order, self.expected)
        self.assertEqual(self.ledger.get_order(self.order)["state"], "deposit_final")

    def test_same_chain_event_cannot_be_credited_to_two_orders(self):
        second = self.ledger.create_order(
            direction="usdt_to_soby", source_network="ethereum",
            destination_network="sobya", deposit_address=INVENTORY,
            source_wallet=SENDER, destination_wallet="0x" + "ee" * 20,
            source_asset=TOKEN, destination_asset="SOBY",
            source_amount=1000, destination_amount=2000,
        )
        class Verifier:
            def verify(inner, expected):
                return self.verified
        recorder = InventoryDepositRecorder(self.ledger)
        recorder.verify_and_record(Verifier(), self.order, self.expected)
        with self.assertRaises(CustodialOrderError):
            recorder.verify_and_record(Verifier(), second, self.expected)


if __name__ == "__main__":
    unittest.main()
