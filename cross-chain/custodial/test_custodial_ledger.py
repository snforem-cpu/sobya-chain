import tempfile, unittest
from pathlib import Path
from custodial_ledger import CustodialOrderError, CustodialOrderLedger

class CustodialLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = CustodialOrderLedger(Path(self.tmp.name) / "orders.sqlite")
        self.order = self.make_order("0xUnique1")
    def tearDown(self):
        self.tmp.cleanup()
    def make_order(self, address):
        return self.ledger.create_order(direction="usdt_to_soby",source_network="ethereum",
            destination_network="sobya",deposit_address=address,source_wallet="0xUser",
            destination_wallet="soby1recipient",source_asset="USDT-ETH",destination_asset="SOBY",
            source_amount=1000000,destination_amount=2000000)
    def test_finalized_deposit_then_payout_completes(self):
        self.assertTrue(self.ledger.record_deposit(self.order,tx_id="0xdeposit",event_index=3,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH"))
        self.assertFalse(self.ledger.record_deposit(self.order,tx_id="0xdeposit",event_index=3,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH"))
        self.ledger.confirm_deposit_final(self.order,verified=True)
        self.ledger.submit_payout(self.order,payout_tx="0xpayout")
        self.ledger.confirm_payout_final(self.order,verified=True,observed_amount=2000000,observed_recipient="soby1recipient",observed_asset="SOBY")
        self.assertEqual(self.ledger.get_order(self.order)["state"],"complete")
    def test_unfinalized_deposit_cannot_pay(self):
        self.ledger.record_deposit(self.order,tx_id="0xdeposit",event_index=0,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH")
        with self.assertRaises(CustodialOrderError):
            self.ledger.submit_payout(self.order,payout_tx="0xpayout")
    def test_false_finality_rejected(self):
        self.ledger.record_deposit(self.order,tx_id="0xdeposit",event_index=0,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH")
        with self.assertRaises(CustodialOrderError):
            self.ledger.confirm_deposit_final(self.order,verified=False)
    def test_replayed_event_cannot_fund_two_orders(self):
        other=self.make_order("0xUnique2")
        self.ledger.record_deposit(self.order,tx_id="0xshared",event_index=1,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH")
        with self.assertRaises(CustodialOrderError):
            self.ledger.record_deposit(other,tx_id="0xshared",event_index=1,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH")
    def test_unique_deposit_address_required(self):
        with self.assertRaises(CustodialOrderError):
            self.make_order("0xUnique1")
    def test_payout_tx_is_idempotent(self):
        self.ledger.record_deposit(self.order,tx_id="0xdeposit",event_index=0,observed_amount=1000000,observed_recipient="0xUnique1",observed_asset="USDT-ETH")
        self.ledger.confirm_deposit_final(self.order,verified=True)
        self.ledger.submit_payout(self.order,payout_tx="0xpayout")
        self.ledger.submit_payout(self.order,payout_tx="0xpayout")
        self.assertEqual(self.ledger.get_order(self.order)["state"],"payout_submitted")

if __name__ == "__main__":
    unittest.main()
