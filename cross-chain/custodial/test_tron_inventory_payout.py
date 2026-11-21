import unittest
from types import SimpleNamespace

from tron_inventory_payout import TronUsdtPayoutAdapter
from payout_executor import PayoutError, PayoutIntent

INVENTORY = "TQ8tU9BJJc67mLvick7Mp24HSMhpcd6kZx"
DESTINATION = "TJRabPrwbZy45sbavfcaxs9DqZ3g4w8p8"
TOKEN = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
AMOUNT = 1_250_000
TXID = "ab" * 32


class FakeSignedTransaction:
    txid = TXID
    def to_json(self):
        return {"raw_data": {"contract": []}, "signature": ["signed"]}


class FakeBuilder:
    def with_owner(self, owner):
        self.owner = owner
        return self
    def fee_limit(self, limit):
        self.limit = limit
        return self
    def build(self):
        return FakeSignedTransaction()
    def sign(self, key):
        return self


class FakeContract:
    class Functions:
        def decimals(self):
            return 6
        def transfer(self, destination, amount):
            self.destination, self.amount = destination, amount
            return FakeBuilder()
    functions = Functions()


class FakeKey:
    class PublicKey:
        def to_base58check_address(self):
            return INVENTORY
    public_key = PublicKey()


class FakeClient:
    def get_contract(self, address):
        return FakeContract()
    def to_hex_address(self, address):
        values = {
            TOKEN: "41" + "11" * 20,
            INVENTORY: "41" + "22" * 20,
            DESTINATION: "41" + "33" * 20,
        }
        return values[address]
    def get_solid_transaction_info(self, txid):
        return {
            "id": txid,
            "blockNumber": 123,
            "receipt": {"result": "SUCCESS"},
            "log": [{
                "address": "41" + "11" * 20,
                "topics": [
                    "0x" + "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x" + "00" * 12 + "22" * 20,
                    "0x" + "00" * 12 + "33" * 20,
                ],
                "data": hex(AMOUNT),
            }],
        }


class TronInventoryPayoutTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TronUsdtPayoutAdapter(
            client=FakeClient(), private_key=FakeKey(),
            inventory_wallet=INVENTORY, usdt_contract=TOKEN,
        )

    def test_prepare_persists_signed_transaction_payload(self):
        intent = PayoutIntent("order-tron", "tron", "USDT-TRON", AMOUNT, DESTINATION)
        prepared = self.adapter.prepare(intent)
        self.assertEqual(prepared.tx_id, TXID)
        self.assertIn(b'"signature":["signed"]', prepared.signed_payload)

    def test_finalized_solid_receipt_must_match_exact_transfer(self):
        intent = PayoutIntent("order-tron", "tron", "USDT-TRON", AMOUNT, DESTINATION)
        self.assertTrue(self.adapter.verify_finalized(intent, TXID))
        wrong = PayoutIntent("order-tron", "tron", "USDT-TRON", AMOUNT + 1, DESTINATION)
        self.assertFalse(self.adapter.verify_finalized(wrong, TXID))

    def test_wrong_asset_rejected_before_signing(self):
        with self.assertRaises(PayoutError):
            self.adapter.prepare(PayoutIntent("order-tron", "tron", "OTHER", AMOUNT, DESTINATION))


if __name__ == "__main__":
    unittest.main()
