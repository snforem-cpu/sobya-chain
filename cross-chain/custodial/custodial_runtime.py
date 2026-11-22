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
    """Build fail-closed USDT-to-SOBY quotes from finalized orders and live SOBYA balance."""
    import sqlite3
    from datetime import datetime, timezone, timedelta

    pricing = config.get("pricing")
    limits = config.get("limits")
    networks = config.get("networks")
    if not isinstance(pricing, dict) or not isinstance(limits, dict) or not isinstance(networks, dict):
        raise DepositRuntimeConfigurationError("pricing, limits, and network configuration are required")
    sobya = networks.get("sobya")
    if not isinstance(sobya, dict):
        raise DepositRuntimeConfigurationError("SOBYA inventory configuration is missing")
    rpc_env = sobya.get("rpcUrlEnv")
    rpc_url = os.environ.get(rpc_env, "") if isinstance(rpc_env, str) else ""
    wallet = sobya.get("inventoryWallet")
    chain_id = sobya.get("chainId")
    if not isinstance(rpc_url, str) or not rpc_url.startswith("https://"):
        raise DepositRuntimeConfigurationError("SOBYA HTTPS RPC endpoint is required for live inventory verification")
    if not isinstance(wallet, str) or len(wallet) != 42 or not wallet.startswith("0x"):
        raise DepositRuntimeConfigurationError("valid SOBYA inventory wallet is required")
    if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
        raise DepositRuntimeConfigurationError("SOBYA chain ID is invalid")
    if ledger is None or not getattr(ledger, "database", None):
        raise DepositRuntimeConfigurationError("durable order ledger is required for demand and inventory limits")

    fee_bps = limits.get("feeBps")
    max_order = limits.get("maxOrderUsdtBaseUnits")
    daily_cap = limits.get("maxDailyUsdtBaseUnitsPerNetwork")
    minimum_inventory = limits.get("minimumInventoryBaseUnits")
    liquidity = pricing.get("referenceLiquidityUsdtBaseUnits")
    for value, label in ((liquidity, "reference liquidity"), (max_order, "maximum order"),
                         (daily_cap, "daily network cap"), (minimum_inventory, "minimum SOBY inventory")):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= 2**256 - 1:
            raise DepositRuntimeConfigurationError(f"positive uint256 operator-approved {label} is required")
    if not isinstance(fee_bps, int) or isinstance(fee_bps, bool) or not 0 <= fee_bps <= 1000:
        raise DepositRuntimeConfigurationError("feeBps must be operator-approved and between 0 and 1000 (10%)")
    try:
        floor_d, ceiling_d = Decimal(str(pricing.get("priceFloor"))), Decimal(str(pricing.get("priceCeiling")))
        base_price = Decimal(str(pricing.get("baseReferencePriceUsdtPerSoby")))
    except Exception as exc:
        raise DepositRuntimeConfigurationError("base price and positive price floor/ceiling are required") from exc
    if (not all(x.is_finite() for x in (floor_d, ceiling_d, base_price))
            or base_price <= 0 or floor_d <= 0 or floor_d >= ceiling_d):
        raise DepositRuntimeConfigurationError("base price and bounds must be finite and positive; floor < ceiling")
    lifetime = limits.get("quoteLifetimeSeconds", 120)
    if not isinstance(lifetime, int) or isinstance(lifetime, bool) or not 15 <= lifetime <= 900:
        raise DepositRuntimeConfigurationError("quote lifetime must be between 15 and 900 seconds")
    window = pricing.get("demandWindowSeconds", 3600)
    max_demand_age = pricing.get("demandMaxAgeSeconds", 300)
    max_inventory_age = pricing.get("inventorySnapshotMaxAgeSeconds", 300)
    up_sensitivity = pricing.get("upwardDemandSensitivityBps", 10000)
    down_sensitivity = pricing.get("downwardDemandSensitivityBps", 2500)
    if not isinstance(window, int) or isinstance(window, bool) or window != 3600:
        raise DepositRuntimeConfigurationError("demandWindowSeconds must be 3600")
    if not isinstance(max_demand_age, int) or not 1 <= max_demand_age <= 900:
        raise DepositRuntimeConfigurationError("demandMaxAgeSeconds must be between 1 and 900")
    if not isinstance(max_inventory_age, int) or not 1 <= max_inventory_age <= 900:
        raise DepositRuntimeConfigurationError("inventorySnapshotMaxAgeSeconds must be between 1 and 900")

    rpc = JsonRpc(rpc_url)

    def provide(direction: str, source_network: str, source_amount: int) -> dict[str, Any]:
        if direction != "usdt_to_soby" or source_network not in ("ethereum", "tron", "solana"):
            raise DepositRuntimeConfigurationError("only USDT-to-SOBY quotes are supported in this release")
        if not isinstance(source_amount, int) or isinstance(source_amount, bool) or not 0 < source_amount <= max_order:
            raise DepositRuntimeConfigurationError("order amount exceeds the configured positive maximum")
        try:
            observed_chain = int(rpc.call("eth_chainId", []), 16)
            if observed_chain != chain_id:
                raise DepositRuntimeConfigurationError("SOBYA RPC chain ID does not match configured chain ID")
            finalized_block = rpc.call("eth_getBlockByNumber", ["finalized", False])
            if not isinstance(finalized_block, dict) or not isinstance(finalized_block.get("number"), str):
                raise DepositRuntimeConfigurationError("SOBYA RPC does not provide a finalized block")
            block_number = int(finalized_block["number"], 16)
            observed_at = int(finalized_block["timestamp"], 16)
            inventory_balance = int(rpc.call("eth_getBalance", [wallet, hex(block_number)]), 16)
        except DepositRuntimeConfigurationError:
            raise
        except Exception as exc:
            raise DepositRuntimeConfigurationError("could not verify SOBYA native balance at finalized block") from exc
        now = int(time.time())
        if observed_at > now or now - observed_at > max_inventory_age:
            raise DepositRuntimeConfigurationError("finalized SOBYA inventory observation is stale or future-dated")
        if inventory_balance <= minimum_inventory:
            raise DepositRuntimeConfigurationError("live SOBY inventory must exceed the protected minimum reserve")

        # Demand is derived only from completed orders: the ledger reaches complete
        # only after the destination payout has independently passed chain finality.
        cutoff = datetime.fromtimestamp(now - window, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(ledger.database, timeout=15) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS custodial_order_quote_expiry (
                order_id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL
            )""")
            demand_rows = db.execute("""SELECT direction, source_amount FROM custodial_orders
                WHERE state='complete' AND created_at >= ? AND direction IN ('usdt_to_soby','soby_to_usdt')""",
                (cutoff,)).fetchall()
            eligible = """(o.state IN ('deposit_seen','deposit_final','payout_submitted','complete')
                OR (o.state='created' AND (q.expires_at IS NULL OR q.expires_at > ?)))"""
            daily_rows = db.execute(f"""SELECT o.source_amount FROM custodial_orders o
                LEFT JOIN custodial_order_quote_expiry q ON q.order_id=o.order_id
                WHERE o.source_network=? AND o.direction='usdt_to_soby'
                AND o.created_at >= date('now') AND {eligible}""",
                (source_network, now)).fetchall()
            reserved_rows = db.execute(f"""SELECT o.destination_amount FROM custodial_orders o
                LEFT JOIN custodial_order_quote_expiry q ON q.order_id=o.order_id
                WHERE o.direction='usdt_to_soby' AND
                (o.state IN ('deposit_seen','deposit_final','payout_submitted')
                OR (o.state='created' AND (q.expires_at IS NULL OR q.expires_at > ?)))""",
                (now,)).fetchall()
        buy_volume = sum(int(amount) for direction, amount in demand_rows if direction == "usdt_to_soby")
        sell_volume = sum(int(amount) for direction, amount in demand_rows if direction == "soby_to_usdt")
        snapshot = DemandSnapshot(buy_volume, sell_volume, window, now, True)
        price = calculate_demand_price(
            base_price_usdt_per_soby=base_price,
            reference_liquidity_usdt_base_units=liquidity,
            snapshot=snapshot, now_epoch=now,
            expected_window_seconds=window, max_snapshot_age_seconds=max_demand_age,
            upward_sensitivity_bps=up_sensitivity, downward_sensitivity_bps=down_sensitivity,
        )
        if not floor_d <= price.quoted_price_usdt_per_soby <= ceiling_d:
            raise DepositRuntimeConfigurationError("demand-adjusted price is outside operator-approved price bounds")
        gross = (Decimal(source_amount) / Decimal(10**6) / price.quoted_price_usdt_per_soby) * Decimal(10**18)
        net = int((gross * Decimal(10000 - fee_bps) / Decimal(10000)).to_integral_value(rounding=ROUND_DOWN))
        if net <= 0:
            raise DepositRuntimeConfigurationError("quoted destination amount rounds to zero")
        daily = sum(int(row[0]) for row in daily_rows)
        reserved = sum(int(row[0]) for row in reserved_rows)
        if daily + source_amount > daily_cap:
            raise DepositRuntimeConfigurationError("daily USDT intake limit for this network would be exceeded")
        if inventory_balance - reserved - net < minimum_inventory:
            raise DepositRuntimeConfigurationError("SOBY payout would breach the protected minimum inventory reserve")
        return {
            "destination_amount": net, "rate": str(price.quoted_price_usdt_per_soby),
            "fee_bps": fee_bps, "expires_at": now + lifetime,
            "executable": True, "inventory_block": hex(block_number),
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
