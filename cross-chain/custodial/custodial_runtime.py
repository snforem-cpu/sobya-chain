"""Unified deposit-verification and payout runtime for the custodial swap worker.

Deposit proofs are submitted by the order/API layer into a durable SQLite queue.
This process verifies each proof against finalized chain state, advances only the
matching order to deposit_final, then lets the existing payout worker process it.
No wallet signing occurs in the deposit path.
"""
from __future__ import annotations

import json
import logging
import time
from decimal import Decimal, ROUND_DOWN
import os
import signal
import threading
from pathlib import Path
from typing import Any

from custodial_ledger import CustodialOrderLedger
from inventory_deposit_watchers import (
    EvmInventoryDepositVerifier,
    InventoryDepositService,
    InventoryDepositWorker,
    JsonRpc,
    SolanaInventoryDepositVerifier,
    TronInventoryDepositVerifier,
)
from payout_runtime import build_inventory_payout_executor
from payout_worker import InventoryPayoutWorker
from demand_pricing import DemandSnapshot, calculate_demand_price
from custodial_order_api import create_server as create_order_api_server

LOG = logging.getLogger("sobya.custodial.runtime")
NETWORK_NAMES = ("ethereum", "tron", "solana", "sobya")


class DepositRuntimeConfigurationError(ValueError):
    pass


def build_inventory_deposit_verifiers(config: dict[str, Any]) -> dict[str, Any]:
    """Build only explicitly enabled read-only verifiers from operator config."""
    if not isinstance(config, dict) or config.get("mode") != "custodial-inventory":
        raise DepositRuntimeConfigurationError("custodial inventory configuration is required")
    networks = config.get("networks")
    if not isinstance(networks, dict):
        raise DepositRuntimeConfigurationError("network configuration is malformed")
    if config.get("depositWatchEnabled") is not True:
        return {}

    verifiers: dict[str, Any] = {}
    for name in NETWORK_NAMES:
        item = networks.get(name)
        if not isinstance(item, dict):
            raise DepositRuntimeConfigurationError(f"{name} configuration is missing")
        if item.get("depositWatchEnabled") is not True:
            continue
        env_name = item.get("rpcUrlEnv")
        rpc_url = os.environ.get(env_name, "") if isinstance(env_name, str) else ""
        if not rpc_url.startswith("https://"):
            raise DepositRuntimeConfigurationError(f"{name} HTTPS RPC endpoint is missing")
        if name in {"ethereum", "sobya"}:
            chain_id = item.get("chainId")
            if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
                raise DepositRuntimeConfigurationError(f"{name} chain ID is invalid")
            verifiers[name] = EvmInventoryDepositVerifier(JsonRpc(rpc_url), chain_id)
        elif name == "tron":
            verifiers[name] = TronInventoryDepositVerifier(rpc_url)
        elif name == "solana":
            token_program = item.get("tokenProgram")
            if not isinstance(token_program, str) or not token_program:
                raise DepositRuntimeConfigurationError("Solana token program is missing")
            verifiers[name] = SolanaInventoryDepositVerifier(JsonRpc(rpc_url), token_program)
    return verifiers



def build_order_quote_provider(config: dict[str, Any], ledger: Any = None):
    """Build bounded, fail-closed USDT-to-SOBY quotes against verified SOBY inventory."""
    import sqlite3

    pricing = config.get("pricing")
    limits = config.get("limits")
    if not isinstance(pricing, dict) or not isinstance(limits, dict):
        raise DepositRuntimeConfigurationError("order API pricing and limits configuration is required")
    snapshot_data = pricing.get("demandSnapshot")
    liquidity = pricing.get("referenceLiquidityUsdtBaseUnits")
    fee_bps = limits.get("feeBps")
    max_order = limits.get("maxOrderUsdtBaseUnits")
    daily_cap = limits.get("maxDailyUsdtBaseUnitsPerNetwork")
    minimum_inventory = limits.get("minimumInventoryBaseUnits")
    ceiling = pricing.get("priceCeiling")
    floor = pricing.get("priceFloor")
    inventory = config.get("networks", {}).get("sobya", {})
    inventory_balance = inventory.get("verifiedPayoutInventoryBaseUnits")
    inventory_observed = inventory.get("inventoryObservedAtEpoch")
    if not isinstance(snapshot_data, dict):
        raise DepositRuntimeConfigurationError("finalized demand snapshot is not configured")
    for value, label in ((liquidity, "reference liquidity"), (max_order, "maximum order"),
                         (daily_cap, "daily network cap"), (minimum_inventory, "minimum SOBY inventory"),
                         (inventory_balance, "verified SOBY payout inventory")):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise DepositRuntimeConfigurationError(f"positive operator-approved {label} is required")
    if not isinstance(inventory_observed, int) or isinstance(inventory_observed, bool):
        raise DepositRuntimeConfigurationError("verified SOBY inventory observation timestamp is required")
    inventory_max_age = pricing.get("inventorySnapshotMaxAgeSeconds", 300)
    if not isinstance(inventory_max_age, int) or isinstance(inventory_max_age, bool) or not 30 <= inventory_max_age <= 900:
        raise DepositRuntimeConfigurationError("inventorySnapshotMaxAgeSeconds must be between 30 and 900")
    if int(time.time()) - inventory_observed not in range(0, inventory_max_age + 1):
        raise DepositRuntimeConfigurationError("verified SOBY inventory snapshot is future-dated or older than 300 seconds")
    if inventory_balance <= minimum_inventory:
        raise DepositRuntimeConfigurationError("verified SOBY inventory must exceed the protected minimum reserve")
    if not isinstance(fee_bps, int) or isinstance(fee_bps, bool) or not 0 <= fee_bps <= 1000:
        raise DepositRuntimeConfigurationError("feeBps must be operator-approved and between 0 and 1000 (10%)")
    try:
        floor_d, ceiling_d = Decimal(str(floor)), Decimal(str(ceiling))
    except Exception as exc:
        raise DepositRuntimeConfigurationError("positive priceFloor and priceCeiling are required") from exc
    if not floor_d.is_finite() or not ceiling_d.is_finite() or floor_d <= 0 or floor_d >= ceiling_d:
        raise DepositRuntimeConfigurationError("price bounds must be finite, positive, and floor < ceiling")
    if not isinstance(snapshot_data, dict):
        raise DepositRuntimeConfigurationError("finalized demand snapshot is not configured")
    try:
        snapshot = DemandSnapshot(
            buy_usdt_base_units=snapshot_data["buyUsdtBaseUnits"],
            sell_usdt_base_units=snapshot_data["sellUsdtBaseUnits"],
            window_seconds=snapshot_data["windowSeconds"],
            observed_at_epoch=snapshot_data["observedAtEpoch"],
            finalized=snapshot_data["finalized"],
        )
    except (KeyError, TypeError) as exc:
        raise DepositRuntimeConfigurationError("finalized demand snapshot schema is invalid") from exc

    def provide(direction: str, source_network: str, source_amount: int) -> dict[str, Any]:
        if direction != "usdt_to_soby" or source_network not in ("ethereum", "tron", "solana"):
            raise DepositRuntimeConfigurationError("only USDT-to-SOBY quotes are supported in this release")
        if not isinstance(source_amount, int) or isinstance(source_amount, bool) or not 0 < source_amount <= max_order:
            raise DepositRuntimeConfigurationError("order amount exceeds the configured positive maximum")
        if ledger is None:
            raise DepositRuntimeConfigurationError("durable order ledger is required for daily and inventory limits")
        price = calculate_demand_price(
            base_price_usdt_per_soby=pricing.get("baseReferencePriceUsdtPerSoby"),
            reference_liquidity_usdt_base_units=liquidity,
            snapshot=snapshot, now_epoch=int(time.time()),
            expected_window_seconds=pricing.get("demandWindowSeconds", 3600),
            max_snapshot_age_seconds=pricing.get("demandMaxAgeSeconds", 300),
            upward_sensitivity_bps=pricing.get("upwardDemandSensitivityBps", 10000),
            downward_sensitivity_bps=pricing.get("downwardDemandSensitivityBps", 2500),
        )
        if not floor_d <= price.quoted_price_usdt_per_soby <= ceiling_d:
            raise DepositRuntimeConfigurationError("demand-adjusted price is outside operator-approved price bounds")
        gross = (Decimal(source_amount) / Decimal(10**6) / price.quoted_price_usdt_per_soby) * Decimal(10**18)
        net = int((gross * Decimal(10000 - fee_bps) / Decimal(10000)).to_integral_value(rounding=ROUND_DOWN))
        if net <= 0:
            raise DepositRuntimeConfigurationError("quoted destination amount rounds to zero")
        lifetime = limits.get("quoteLifetimeSeconds", 120)
        if not isinstance(lifetime, int) or isinstance(lifetime, bool) or not 15 <= lifetime <= 900:
            raise DepositRuntimeConfigurationError("quote lifetime must be between 15 and 900 seconds")
        # Check daily intake and outstanding SOBY obligations against the same durable ledger.
        with sqlite3.connect(ledger.database, timeout=15) as db:
            daily_rows = db.execute("""SELECT source_amount FROM custodial_orders
                WHERE source_network=? AND direction='usdt_to_soby'
                AND created_at >= date('now')""", (source_network,)).fetchall()
            reserved_rows = db.execute("""SELECT destination_amount FROM custodial_orders
                WHERE direction='usdt_to_soby'
                AND state IN ('created','deposit_seen','deposit_final','payout_submitted')""").fetchall()
        # Amounts are uint256 decimal strings; never aggregate them through SQLite's int64 CAST/SUM.
        daily = sum(int(row[0]) for row in daily_rows)
        reserved = sum(int(row[0]) for row in reserved_rows)
        if daily + source_amount > daily_cap:
            raise DepositRuntimeConfigurationError("daily USDT intake limit for this network would be exceeded")
        if inventory_balance - reserved - net < minimum_inventory:
            raise DepositRuntimeConfigurationError("SOBY payout would breach the protected minimum inventory reserve")
        return {
            "destination_amount": net, "rate": str(price.quoted_price_usdt_per_soby),
            "fee_bps": fee_bps, "expires_at": int(time.time()) + lifetime,
            "executable": True,
        }
    return provide


class CustodialDepositPayoutRuntime:
    """Run deposit verification before payout processing on every poll cycle."""

    def __init__(self, ledger: Any, deposit_worker: InventoryDepositWorker,
                 payout_worker: InventoryPayoutWorker):
        self.ledger = ledger
        self.deposit_worker = deposit_worker
        self.payout_worker = payout_worker

    def run_once(self) -> dict[str, dict[str, int]]:
        deposits = self.deposit_worker.run_once()
        payouts = self.payout_worker.run_once()
        return {"deposits": deposits, "payouts": payouts}

    def run_forever(self, stop_event: threading.Event, *, interval_seconds: int = 5) -> None:
        if not 1 <= interval_seconds <= 300:
            raise ValueError("poll interval must be between 1 and 300 seconds")
        while not stop_event.is_set():
            result = self.run_once()
            if any(result["deposits"].values()) or any(result["payouts"].values()):
                LOG.info("custodial cycle deposits=%s payouts=%s",
                         result["deposits"], result["payouts"])
            stop_event.wait(interval_seconds)


def main() -> int:
    config_path = Path(os.environ.get("SOBYA_CUSTODIAL_CONFIG", "config.json")).expanduser()
    ledger_path = Path(os.environ.get("SOBYA_CUSTODIAL_DB", "data/orders.sqlite3")).expanduser()
    interval = int(os.environ.get("SOBYA_CUSTODIAL_POLL_SECONDS", "5"))
    if not config_path.is_file():
        raise SystemExit("custodial config file is missing; refusing to start")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    ledger_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger = CustodialOrderLedger(ledger_path)

    verifiers = build_inventory_deposit_verifiers(config)
    deposit_service = InventoryDepositService(ledger, verifiers)
    deposit_worker = InventoryDepositWorker(deposit_service, str(ledger_path))
    payout_executor = build_inventory_payout_executor(
        config, ledger, os.environ.get("SOBYA_PAYOUT_JOURNAL", "data/payout-journal.sqlite3")
    )
    payout_worker = InventoryPayoutWorker(ledger, payout_executor)
    runtime = CustodialDepositPayoutRuntime(ledger, deposit_worker, payout_worker)

    order_api = None
    order_api_thread = None
    if config.get("orderApiEnabled") is True:
        secret_env = config.get("orderApiAccessSecretEnv", "SOBYA_ORDER_API_ACCESS_SECRET")
        secret = os.environ.get(secret_env, "") if isinstance(secret_env, str) else ""
        quote_provider = build_order_quote_provider(config, ledger)
        order_api = create_order_api_server(
            config.get("orderApiHost", "127.0.0.1"),
            int(config.get("orderApiPort", 8765)), ledger, deposit_worker,
            config=config, quote_provider=quote_provider, access_secret=secret,
        )
        order_api_thread = threading.Thread(target=order_api.serve_forever, daemon=True)
        order_api_thread.start()
        LOG.info("SOBYA order API started on loopback port %s", order_api.server_address[1])

    if not verifiers:
        LOG.info("deposit verification is disabled; no deposit RPC clients were created")
    if not payout_executor.enabled:
        LOG.info("custodial payouts are disabled; no payout wallet adapters were created")

    stop = threading.Event()

    def request_stop(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    LOG.info("SOBYA unified custodial runtime started; poll interval=%s seconds", interval)
    try:
        runtime.run_forever(stop, interval_seconds=interval)
    finally:
        if order_api is not None:
            order_api.shutdown()
            order_api.server_close()
            if order_api_thread is not None:
                order_api_thread.join(timeout=5)
        LOG.info("SOBYA unified custodial runtime stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
