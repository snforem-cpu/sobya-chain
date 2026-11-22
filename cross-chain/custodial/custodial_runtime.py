"""Unified deposit-verification and payout runtime for the custodial swap worker.

Deposit proofs are submitted by the order/API layer into a durable SQLite queue.
This process verifies each proof against finalized chain state, advances only the
matching order to deposit_final, then lets the existing payout worker process it.
No wallet signing occurs in the deposit path.
"""
from __future__ import annotations

import json
import logging
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
        LOG.info("SOBYA unified custodial runtime stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
