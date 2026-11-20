"""Deterministic, inventory-aware cross-chain quote pricing.

Rates are operator-published rational reference prices, never inferred from a
user deposit. Amounts are integer token base units. This module does not sign
quotes, read a market feed, or claim that a manual rate is a market price.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

from order_ledger import OrderQuote


class PricingError(ValueError):
    pass


@dataclass(frozen=True)
class PricingConfig:
    # USDT atomic units per one whole SOBY, represented as a rational.
    usdt_atoms_numerator: int
    soby_whole_denominator: int = 1
    usdt_decimals: int = 6
    soby_decimals: int = 18
    fee_bps: int = 100
    min_source_amount: int = 1
    max_source_amount: int = 0
    quote_ttl_seconds: int = 120
    refund_grace_seconds: int = 3600

    def validate(self) -> None:
        if self.usdt_atoms_numerator <= 0 or self.soby_whole_denominator <= 0:
            raise PricingError("a positive rational USDT/SOBY reference rate is required")
        if not 0 <= self.fee_bps < 10_000:
            raise PricingError("fee_bps must be between 0 and 9999")
        if self.usdt_decimals < 0 or self.soby_decimals < 0:
            raise PricingError("token decimals cannot be negative")
        if self.min_source_amount <= 0 or self.max_source_amount < self.min_source_amount:
            raise PricingError("invalid source amount limits")
        if self.quote_ttl_seconds < 15 or self.refund_grace_seconds <= self.quote_ttl_seconds:
            raise PricingError("quote TTL/refund grace configuration is unsafe")


class InventoryAwareQuotePricer:
    """Build a quote only when the local ledger has enough unreserved SOBY."""

    def __init__(
        self,
        config: PricingConfig,
        ledger,
        *,
        destination_chain_id: int,
        now: Callable[[], int] | None = None,
    ):
        config.validate()
        if not isinstance(destination_chain_id, int) or destination_chain_id <= 0:
            raise PricingError("destination chain ID must be positive")
        self.config = config
        self.ledger = ledger
        self.destination_chain_id = destination_chain_id
        self.now = now or (lambda: int(time.time()))

    def quote(
        self,
        *,
        order_id: str,
        source_chain: str,
        source_asset: str,
        source_amount: int,
        user: str,
        solver: str,
        destination_recipient: str,
    ) -> OrderQuote:
        c = self.config
        if not isinstance(source_amount, int) or isinstance(source_amount, bool):
            raise PricingError("source amount must be an integer number of token base units")
        if source_amount < c.min_source_amount or source_amount > c.max_source_amount:
            raise PricingError("source amount is outside configured limits")
        if not all(isinstance(v, str) and v.strip() for v in (
            order_id, source_chain, source_asset, user, solver, destination_recipient
        )):
            raise PricingError("quote identity fields are required")

        # Net source proceeds after fee, then convert USDT atoms to SOBY atoms.
        net_source = source_amount * (10_000 - c.fee_bps) // 10_000
        numerator = net_source * (10 ** c.soby_decimals) * c.soby_whole_denominator
        denominator = c.usdt_atoms_numerator
        destination_amount = numerator // denominator
        if destination_amount <= 0:
            raise PricingError("source amount is too small to produce a positive SOBY payout")

        available = self.ledger.available_solver_inventory(solver)
        if not isinstance(available, int) or available < destination_amount:
            raise PricingError("solver has insufficient unreserved SOBY inventory")

        current = int(self.now())
        quote_expiry = current + c.quote_ttl_seconds
        refund_after = current + c.refund_grace_seconds
        return OrderQuote(
            order_id=order_id,
            source_chain=source_chain.lower(),
            source_asset=source_asset,
            source_amount=source_amount,
            user=user,
            solver=solver,
            destination_chain_id=self.destination_chain_id,
            destination_recipient=destination_recipient,
            destination_amount=destination_amount,
            quote_expiry=quote_expiry,
            refund_after=refund_after,
        )
