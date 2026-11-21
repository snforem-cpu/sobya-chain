import unittest
from decimal import Decimal
from demand_pricing import DemandSnapshot, PricingError, calculate_demand_price

class DemandPricingTests(unittest.TestCase):
    def snapshot(self, buy, sell, age=10, window=3600, finalized=True):
        return DemandSnapshot(buy, sell, window, 1000-age, finalized)
    def quote(self, snap, liquidity=1000):
        return calculate_demand_price(base_price_usdt_per_soby="0.005",
            reference_liquidity_usdt_base_units=liquidity, snapshot=snap,
            now_epoch=1000, expected_window_seconds=3600,
            max_snapshot_age_seconds=300, upward_sensitivity_bps=10000,
            downward_sensitivity_bps=2500)
    def test_buy_pressure_rises_without_configured_ceiling(self):
        one=self.quote(self.snapshot(1000,0)); ten=self.quote(self.snapshot(10000,0))
        self.assertGreater(one.quoted_price_usdt_per_soby, Decimal("0.005"))
        self.assertGreater(ten.quoted_price_usdt_per_soby, one.quoted_price_usdt_per_soby)
        self.assertGreater(ten.quoted_price_usdt_per_soby, Decimal("0.1"))
    def test_upward_move_exceeds_equal_sell_move(self):
        buy=self.quote(self.snapshot(1000,0)); sell=self.quote(self.snapshot(0,1000))
        self.assertGreater(buy.quoted_price_usdt_per_soby-Decimal("0.005"),
                           Decimal("0.005")-sell.quoted_price_usdt_per_soby)
    def test_sell_pressure_decreases_price(self):
        self.assertLess(self.quote(self.snapshot(0,500)).quoted_price_usdt_per_soby,Decimal("0.005"))
    def test_balanced_flow_and_no_flow_do_not_drift_with_time(self):
        for snap in (self.snapshot(500,500), self.snapshot(0,0,age=200)):
            self.assertEqual(self.quote(snap).quoted_price_usdt_per_soby,Decimal("0.005"))
    def test_more_buy_volume_means_higher_price(self):
        self.assertGreater(self.quote(self.snapshot(500,0)).quoted_price_usdt_per_soby,
                           self.quote(self.snapshot(100,0)).quoted_price_usdt_per_soby)
    def test_zero_liquidity_fails_closed(self):
        with self.assertRaises(PricingError): self.quote(self.snapshot(1000,0),0)
    def test_stale_unfinalized_wrong_window_and_future_fail_closed(self):
        for snap in (self.snapshot(100,0,age=301), self.snapshot(100,0,finalized=False),
                     self.snapshot(100,0,window=1800), DemandSnapshot(100,0,3600,1001,True)):
            with self.assertRaises(PricingError): self.quote(snap)
    def test_invalid_base_fails_closed(self):
        for base in (None,0,-1,"bad"):
            with self.assertRaises(PricingError):
                calculate_demand_price(base_price_usdt_per_soby=base,
                    reference_liquidity_usdt_base_units=1000,snapshot=self.snapshot(100,0),now_epoch=1000)
    def test_upward_sensitivity_must_exceed_downward(self):
        with self.assertRaises(PricingError):
            calculate_demand_price(base_price_usdt_per_soby="0.005",
                reference_liquidity_usdt_base_units=1000,snapshot=self.snapshot(100,0),
                now_epoch=1000,upward_sensitivity_bps=1000,downward_sensitivity_bps=1000)

if __name__ == "__main__":
    unittest.main()
