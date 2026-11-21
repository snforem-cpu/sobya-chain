import unittest
from decimal import Decimal
from demand_pricing import DemandSnapshot, PricingError, calculate_demand_price


class DemandPricingTests(unittest.TestCase):
    def snapshot(self, buy, sell, *, age=10, window=3600, finalized=True):
        return DemandSnapshot(buy, sell, window, 1000 - age, finalized)

    def quote(self, snap):
        return calculate_demand_price(
            base_price_usdt_per_soby="0.005",
            snapshot=snap,
            now_epoch=1000,
            expected_window_seconds=3600,
            max_snapshot_age_seconds=300,
            sensitivity_bps=2000,
            max_adjustment_bps=1500,
        )

    def test_buy_pressure_increases_price(self):
        q = self.quote(self.snapshot(900, 100))
        self.assertGreater(q.quoted_price_usdt_per_soby, q.base_price_usdt_per_soby)
        self.assertGreater(q.adjustment_bps, 0)

    def test_sell_pressure_decreases_price(self):
        q = self.quote(self.snapshot(100, 900))
        self.assertLess(q.quoted_price_usdt_per_soby, q.base_price_usdt_per_soby)
        self.assertLess(q.adjustment_bps, 0)

    def test_balanced_flow_keeps_base_price(self):
        q = self.quote(self.snapshot(500, 500))
        self.assertEqual(q.adjustment_bps, 0)
        self.assertEqual(q.quoted_price_usdt_per_soby, Decimal("0.005"))

    def test_adjustment_is_capped(self):
        q = self.quote(self.snapshot(1000, 0))
        self.assertEqual(q.adjustment_bps, 1500)
        self.assertEqual(q.quoted_price_usdt_per_soby, Decimal("0.00575"))

    def test_stale_snapshot_fails_closed(self):
        with self.assertRaises(PricingError):
            self.quote(self.snapshot(1000, 0, age=301))

    def test_unfinalized_snapshot_fails_closed(self):
        with self.assertRaises(PricingError):
            self.quote(self.snapshot(1000, 0, finalized=False))

    def test_wrong_window_fails_closed(self):
        with self.assertRaises(PricingError):
            self.quote(self.snapshot(1000, 0, window=1800))

    def test_missing_or_invalid_base_price_fails_closed(self):
        snap = self.snapshot(1000, 0)
        for base in (None, 0, -1, "not-a-price"):
            with self.subTest(base=base):
                with self.assertRaises(PricingError):
                    calculate_demand_price(
                        base_price_usdt_per_soby=base, snapshot=snap, now_epoch=1000
                    )

    def test_future_snapshot_fails_closed(self):
        snap = DemandSnapshot(100, 0, 3600, 1001, True)
        with self.assertRaises(PricingError):
            self.quote(snap)


if __name__ == "__main__":
    unittest.main()
