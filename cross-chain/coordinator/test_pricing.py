import tempfile
import unittest
from pathlib import Path

from order_ledger import CrossChainOrderLedger
from pricing import InventoryAwareQuotePricer, PricingConfig, PricingError


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CrossChainOrderLedger(str(Path(self.temp.name) / "ledger.sqlite"))
        self.solver = "0x" + "44" * 20
        self.ledger.set_solver_inventory(self.solver, 100 * 10**18)
        self.config = PricingConfig(
            usdt_atoms_numerator=2_000_000, soby_whole_denominator=1,
            fee_bps=100, min_source_amount=1_000_000,
            max_source_amount=100_000_000, quote_ttl_seconds=60,
            refund_grace_seconds=3600,
        )
        self.pricer = InventoryAwareQuotePricer(
            self.config, self.ledger, destination_chain_id=357812033857,
            now=lambda: 1_900_000_000,
        )

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_quote_uses_integer_rational_rate_and_fee(self):
        quote = self.pricer.quote(
            order_id="0x" + "01"*32, source_chain="ethereum",
            source_asset="0x" + "33"*20, source_amount=20_000_000,
            user="0x" + "22"*20, solver=self.solver,
            destination_recipient="0x" + "55"*20,
        )
        self.assertEqual(quote.destination_amount, 9_900_000_000_000_000_000)
        self.assertEqual(quote.quote_expiry, 1_900_000_060)
        self.assertEqual(quote.refund_after, 1_900_003_600)

    def test_insufficient_inventory_rejected(self):
        self.ledger.set_solver_inventory(self.solver, 1)
        with self.assertRaises(PricingError):
            self.pricer.quote(
                order_id="0x" + "01"*32, source_chain="ethereum",
                source_asset="0x" + "33"*20, source_amount=20_000_000,
                user="0x" + "22"*20, solver=self.solver,
                destination_recipient="0x" + "55"*20,
            )

    def test_invalid_amount_and_rate_rejected(self):
        with self.assertRaises(PricingError):
            self.pricer.quote(
                order_id="x", source_chain="ethereum", source_asset="a",
                source_amount=True, user="u", solver=self.solver, destination_recipient="r",
            )
        with self.assertRaises(PricingError):
            PricingConfig(0, max_source_amount=1).validate()


if __name__ == "__main__":
    unittest.main()
