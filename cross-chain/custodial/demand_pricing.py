"""Bounded demand-responsive reference pricing for custodial SOBY/USDT quotes.

The operator supplies the base reference price. This module only applies a
bounded adjustment from finalized, executed swap volume; it is not an oracle,
AMM, or guarantee of market value.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


class PricingError(ValueError):
    pass


@dataclass(frozen=True)
class DemandSnapshot:
    buy_usdt_base_units: int
    sell_usdt_base_units: int
    window_seconds: int
    observed_at_epoch: int
    finalized: bool


@dataclass(frozen=True)
class PriceQuote:
    base_price_usdt_per_soby: Decimal
    quoted_price_usdt_per_soby: Decimal
    adjustment_bps: int
    buy_volume_usdt_base_units: int
    sell_volume_usdt_base_units: int
    window_seconds: int


def calculate_demand_price(
    *,
    base_price_usdt_per_soby,
    snapshot: DemandSnapshot,
    now_epoch: int,
    expected_window_seconds: int = 3600,
    max_snapshot_age_seconds: int = 300,
    sensitivity_bps: int = 2000,
    max_adjustment_bps: int = 1500,
) -> PriceQuote:
    """Return base price adjusted by bounded net finalized buy/sell pressure.

    Buy volume means executed USDT -> SOBY swaps; sell volume means executed
    SOBY -> USDT swaps, both normalized to the same USDT base units.
    """
    try:
        base = Decimal(str(base_price_usdt_per_soby))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PricingError("a valid operator-approved base price is required") from exc
    if not base.is_finite() or base <= 0:
        raise PricingError("base price must be finite and greater than zero")
    if not isinstance(snapshot, DemandSnapshot):
        raise PricingError("a demand snapshot is required")
    for value, label in (
        (snapshot.buy_usdt_base_units, "buy volume"),
        (snapshot.sell_usdt_base_units, "sell volume"),
        (snapshot.window_seconds, "window"),
        (snapshot.observed_at_epoch, "snapshot timestamp"),
        (now_epoch, "current timestamp"),
        (expected_window_seconds, "expected window"),
        (max_snapshot_age_seconds, "maximum snapshot age"),
        (sensitivity_bps, "sensitivity"),
        (max_adjustment_bps, "maximum adjustment"),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise PricingError(f"{label} must be a non-negative integer")
    if snapshot.buy_usdt_base_units < 0 or snapshot.sell_usdt_base_units < 0:
        raise PricingError("volume cannot be negative")
    if snapshot.finalized is not True:
        raise PricingError("demand snapshot must contain finalized executed swaps only")
    if snapshot.window_seconds != expected_window_seconds or expected_window_seconds == 0:
        raise PricingError("demand snapshot window does not match configured window")
    age = now_epoch - snapshot.observed_at_epoch
    if age < 0 or age > max_snapshot_age_seconds:
        raise PricingError("demand snapshot is future-dated or stale")
    if sensitivity_bps > 10000 or max_adjustment_bps > 5000:
        raise PricingError("pricing sensitivity or adjustment cap exceeds safe bounds")

    buy = snapshot.buy_usdt_base_units
    sell = snapshot.sell_usdt_base_units
    total = buy + sell
    adjustment = 0
    if total:
        net = buy - sell
        adjustment = int(Decimal(sensitivity_bps) * Decimal(net) / Decimal(total))
        adjustment = max(-max_adjustment_bps, min(max_adjustment_bps, adjustment))

    quoted = base * (Decimal(10000 + adjustment) / Decimal(10000))
    return PriceQuote(
        base_price_usdt_per_soby=base,
        quoted_price_usdt_per_soby=quoted,
        adjustment_bps=adjustment,
        buy_volume_usdt_base_units=buy,
        sell_volume_usdt_base_units=sell,
        window_seconds=snapshot.window_seconds,
    )
