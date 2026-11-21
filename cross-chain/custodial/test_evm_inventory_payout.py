import unittest
from types import SimpleNamespace

from evm_inventory_payout import EvmInventoryPayoutAdapter
from payout_executor import PayoutError, PayoutIntent

INVENTORY = "0xebdb899fFE84a89e1d576964b640491c135651AD"
RECIPIENT = "0x1111111111111111111111111111111111111111"
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
TX_HASH = bytes.fromhex("ab" * 32)
BLOCK_HASH = bytes.fromhex("cd" * 32)
AMOUNT = 1_234_567


class FakeAccount:
    address = INVENTORY
    def sign_transaction(self, tx):
        self.tx = tx
        return SimpleNamespace(raw_transaction=b"signed-raw", hash=TX_HASH)


class FakeEth:
    def __init__(self, chain_id, network):
        self.chain_id = chain_id
        self.block_number = 100
        self.max_priority_fee = 2
        self.gas_price = 10
        self.network = network
        self.last_tx = None
    def get_transaction_count(self, address, block):
        return 7
    def estimate_gas(self, tx):
        self.last_tx = tx
        return 50_000
    def get_block(self, block):
        if block == "latest":
            return {"baseFeePerGas": 10}
        if block == "finalized":
            return {"number": 100, "hash": BLOCK_HASH}
        return {"number": 90, "hash": BLOCK_HASH}
    def send_raw_transaction(self, raw):
        return TX_HASH
    def get_transaction(self, txid):
        if self.network == "ethereum":
            return {"from": INVENTORY, "to": USDT, "input": b"transfer"}
        return {"from": INVENTORY, "to": RECIPIENT, "value": AMOUNT, "input": b""}
    def get_transaction_receipt(self, txid):
        if self.network == "ethereum":
            topics = [
                bytes.fromhex("ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
                bytes.fromhex("00" * 12 + INVENTORY[2:].lower()),
                bytes.fromhex("00" * 12 + RECIPIENT[2:].lower()),
            ]
            logs = [{"address": USDT, "topics": topics, "data": AMOUNT.to_bytes(32, "big")}]
        else:
            logs = []
        return {"status": 1, "blockNumber": 90, "blockHash": BLOCK_HASH, "logs": logs}


class FakeWeb3:
    def __init__(self, chain_id, network):
        self.eth = FakeEth(chain_id, network)


class EvmInventoryPayoutTests(unittest.TestCase):
    def test_ethereum_usdt_sign_and_finalized_receipt(self):
        web3 = FakeWeb3(1, "ethereum")
        adapter = EvmInventoryPayoutAdapter(
            network="ethereum", web3=web3, account=FakeAccount(), chain_id=1,
            inventory_wallet=INVENTORY, confirmations=10, token_contract=USDT,
        )
        intent = PayoutIntent("order-1", "ethereum", "USDT-ETH", AMOUNT, RECIPIENT)
        prepared = adapter.prepare(intent)
        self.assertEqual(prepared.tx_id, "0x" + "ab" * 32)
        self.assertEqual(web3.eth.last_tx["nonce"], 7)
        self.assertEqual(web3.eth.last_tx["to"], USDT)
        self.assertEqual(adapter.broadcast(prepared), prepared.tx_id)
        self.assertTrue(adapter.verify_finalized(intent, prepared.tx_id))

    def test_sobya_native_soby_sign_and_finalized_receipt(self):
        chain_id = 357812033857
        web3 = FakeWeb3(chain_id, "sobya")
        adapter = EvmInventoryPayoutAdapter(
            network="sobya", web3=web3, account=FakeAccount(), chain_id=chain_id,
            inventory_wallet=INVENTORY, confirmations=2,
        )
        intent = PayoutIntent("order-2", "sobya", "SOBY", AMOUNT, RECIPIENT)
        prepared = adapter.prepare(intent)
        self.assertEqual(web3.eth.last_tx["to"], RECIPIENT)
        self.assertEqual(web3.eth.last_tx["value"], AMOUNT)
        self.assertTrue(adapter.verify_finalized(intent, prepared.tx_id))

    def test_wrong_native_asset_rejected(self):
        web3 = FakeWeb3(357812033857, "sobya")
        adapter = EvmInventoryPayoutAdapter(
            network="sobya", web3=web3, account=FakeAccount(),
            chain_id=357812033857, inventory_wallet=INVENTORY, confirmations=2,
        )
        with self.assertRaises(PayoutError):
            adapter.prepare(PayoutIntent("order-3", "sobya", "WSOBY", AMOUNT, RECIPIENT))


if __name__ == "__main__":
    unittest.main()
