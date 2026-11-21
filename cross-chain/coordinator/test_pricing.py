import tempfile
import unittest
from pathlib import Path

from order_ledger import CrossChainOrderLedger
from pricing import (DemandSnapshot, InventoryAwareQuotePricer, PricingConfig,
                      PricingError, demand_adjustment_bps)


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CrossChainOrderLedger(str(Path(self.temp.name) / "ledger.sqlite"))
        self.solver = "0x" + "44" * 20
        self.ledger.set_solver_inventory(self.solver, 150_000_000 * 10**18)
        self.config = PricingConfig(
            usdt_atoms_numerator=2_000_000, soby_whole_denominator=1,
            fee_bps=100, min_source_amount=1_000_000,
            max_source_amount=100_000_000, quote_ttl_seconds=60,
            refund_grace_seconds=3600,
        )
        self.pricer = InventoryAwareQuotePricer(
            self.config, self.ledger, destination_chain_id=357812033857,
            finalized_balance=lambda _solver: 150_000_000 * 10**18,
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

    def test_large_mainnet_scale_inventory_is_exact(self):
        expected = 150_000_000 * 10**18
        self.assertEqual(self.ledger.available_solver_inventory(self.solver), expected)

    def test_insufficient_inventory_rejected(self):
        self.ledger.set_solver_inventory(self.solver, 1)
        with self.assertRaises(PricingError):
            self.pricer.quote(
                order_id="0x" + "01"*32, source_chain="ethereum",
                source_asset="0x" + "33"*20, source_amount=20_000_000,
                user="0x" + "22"*20, solver=self.solver,
                destination_recipient="0x" + "55"*20,
            )

    def test_quote_rejected_when_finalized_chain_balance_is_below_reservations(self):
        self.ledger.set_solver_inventory(self.solver, 150_000_000 * 10**18)
        pricer = InventoryAwareQuotePricer(
            self.config, self.ledger, destination_chain_id=357812033857,
            finalized_balance=lambda _solver: 0,
            now=lambda: 1_900_000_000,
        )
        with self.assertRaisesRegex(PricingError, "insufficient reconciled"):
            pricer.quote(
                order_id="0x" + "02"*32, source_chain="ethereum",
                source_asset="0x" + "33"*20, source_amount=20_000_000,
                user="0x" + "22"*20, solver=self.solver,
                destination_recipient="0x" + "55"*20,
            )

    def test_vault_available_balance_is_not_double_subtracted(self):
        total = 50 * 10**18
        self.ledger.set_solver_inventory(self.solver, total)
        first = self.pricer.quote(
            order_id="0x" + "31" * 32, source_chain="ethereum",
            source_asset="0x" + "33" * 20, source_amount=80_000_000,
            user="0x" + "22" * 20, solver=self.solver,
            destination_recipient="0x" + "55" * 20,
        )
        self.ledger.register_quote_with_inventory(first, now=1_900_000_000)
        remaining = total - first.destination_amount
        pricer = InventoryAwareQuotePricer(
            self.config, self.ledger, destination_chain_id=357812033857,
            # The vault view is already net of its on-chain reservation.
            finalized_balance=lambda _solver: remaining,
            now=lambda: 1_900_000_000,
        )
        second = pricer.quote(
            order_id="0x" + "32" * 32, source_chain="ethereum",
            source_asset="0x" + "33" * 20, source_amount=20_000_000,
            user="0x" + "22" * 20, solver=self.solver,
            destination_recipient="0x" + "55" * 20,
        )
        self.assertEqual(second.destination_amount, 9_900_000_000_000_000_000)
        self.assertGreaterEqual(remaining, second.destination_amount)

    def test_invalid_amount_and_rate_rejected(self):
        with self.assertRaises(PricingError):
            self.pricer.quote(
                order_id="x", source_chain="ethereum", source_asset="a",
                source_amount=True, user="u", solver=self.solver, destination_recipient="r",
            )
        with self.assertRaises(PricingError):
            PricingConfig(0, max_source_amount=1).validate()


    def test_finalized_net_buy_demand_increases_reference_price(self):
        config = PricingConfig(2_000_000, demand_sensitivity_bps=2_000,
                               max_demand_adjustment_bps=1_500)
        snapshot = DemandSnapshot(900_000_000, 100_000_000, 3600, 1_900_000_000)
        self.assertEqual(demand_adjustment_bps(snapshot, config, 1_900_000_010), 1_600 if False else 1_500)

    def test_finalized_net_sell_demand_reduces_reference_price(self):
        config = PricingConfig(2_000_000, demand_sensitivity_bps=2_000,
                               max_demand_adjustment_bps=1_500)
        snapshot = DemandSnapshot(100_000_000, 900_000_000, 3600, 1_900_000_000)
        self.assertEqual(demand_adjustment_bps(snapshot, config, 1_900_000_010), -1_500)

    def test_pending_or_stale_demand_is_rejected(self):
        config = PricingConfig(2_000_000, demand_sensitivity_bps=2_000,
                               max_demand_adjustment_bps=1_500)
        pending = DemandSnapshot(900, 100, 3600, 1_900_000_000, finalized=False)
        with self.assertRaises(PricingError):
            demand_adjustment_bps(pending, config, 1_900_000_010)
        stale = DemandSnapshot(900, 100, 3600, 1_900_000_000)
        with self.assertRaises(PricingError):
            demand_adjustment_bps(stale, config, 1_900_000_400)

    def test_demand_enabled_without_provider_fails_closed(self):
        config = PricingConfig(
            usdt_atoms_numerator=2_000_000, demand_sensitivity_bps=2_000,
            max_demand_adjustment_bps=1_500, min_source_amount=1_000_000,
            max_source_amount=100_000_000,
        )
        pricer = InventoryAwareQuotePricer(
            config, self.ledger, destination_chain_id=357812033857,
            finalized_balance=lambda _solver: 150_000_000 * 10**18,
            now=lambda: 1_900_000_000,
        )
        with self.assertRaisesRegex(PricingError, "no finalized-volume provider"):
            pricer.quote(
                order_id="0x" + "03"*32, source_chain="ethereum",
                source_asset="0x" + "33"*20, source_amount=20_000_000,
                user="0x" + "22"*20, solver=self.solver,
                destination_recipient="0x" + "55"*20,
            )

if __name__ == "__main__":
    unittest.main()
