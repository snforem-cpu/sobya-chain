"""Asymmetric, uncapped demand-responsive SOBY/USDT reference pricing."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext, DecimalException

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

def calculate_demand_price(*, base_price_usdt_per_soby,
    reference_liquidity_usdt_base_units: int, snapshot: DemandSnapshot,
    now_epoch: int, expected_window_seconds: int = 3600,
    max_snapshot_age_seconds: int = 300, upward_sensitivity_bps: int = 10000,
    downward_sensitivity_bps: int = 2500) -> PriceQuote:
    """Exponential impact; upward coefficient exceeds downward; no price cap/floor."""
    try:
        base = Decimal(str(base_price_usdt_per_soby))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PricingError("valid operator-approved base price required") from exc
    if not base.is_finite() or base <= 0:
        raise PricingError("base price must be finite and positive")
    if not isinstance(snapshot, DemandSnapshot):
        raise PricingError("demand snapshot required")
    values = (
        (snapshot.buy_usdt_base_units, "buy volume"),
        (snapshot.sell_usdt_base_units, "sell volume"),
        (snapshot.window_seconds, "window"),
        (snapshot.observed_at_epoch, "snapshot timestamp"),
        (now_epoch, "current timestamp"),
        (expected_window_seconds, "expected window"),
        (max_snapshot_age_seconds, "maximum snapshot age"),
        (reference_liquidity_usdt_base_units, "reference liquidity"),
        (upward_sensitivity_bps, "upward sensitivity"),
        (downward_sensitivity_bps, "downward sensitivity"),
    )
    for value, label in values:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise PricingError(f"{label} must be a non-negative integer")
    if reference_liquidity_usdt_base_units == 0:
        raise PricingError("verified non-zero reference liquidity required")
    if snapshot.finalized is not True:
        raise PricingError("only finalized executed swaps may be counted")
    if snapshot.window_seconds != expected_window_seconds or expected_window_seconds == 0:
        raise PricingError("snapshot window mismatch")
    age = now_epoch - snapshot.observed_at_epoch
    if age < 0 or age > max_snapshot_age_seconds:
        raise PricingError("snapshot is future-dated or stale")
    if upward_sensitivity_bps == 0 or downward_sensitivity_bps >= upward_sensitivity_bps:
        raise PricingError("upward sensitivity must be positive and exceed downward sensitivity")
    net = snapshot.buy_usdt_base_units - snapshot.sell_usdt_base_units
    with localcontext() as ctx:
        ctx.prec = 50
        pressure = Decimal(abs(net)) / Decimal(reference_liquidity_usdt_base_units)
        sensitivity = Decimal(upward_sensitivity_bps if net >= 0 else downward_sensitivity_bps) / Decimal(10000)
        try:
            factor = (sensitivity * pressure).exp()
            if net < 0:
                factor = Decimal(1) / factor
            quoted = base * factor
        except DecimalException as exc:
            raise PricingError("demand impact exceeds supported numeric precision") from exc
        adjustment = int((factor - Decimal(1)) * Decimal(10000))
    return PriceQuote(base, quoted, adjustment, snapshot.buy_usdt_base_units,
                      snapshot.sell_usdt_base_units, snapshot.window_seconds)
