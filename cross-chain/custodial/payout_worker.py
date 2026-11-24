"""Continuous, restart-safe payout worker for finalized custodial orders.

Deposit watchers remain read-only and write verified orders to the shared ledger.
This worker drains only finalized orders, resumes existing signed payouts, and
never creates a replacement transaction when the durable journal is missing.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any

from custodial_ledger import CustodialOrderLedger
from payout_executor import PayoutError, PayoutPending
from payout_runtime import build_inventory_payout_executor

LOG = logging.getLogger("sobya.custodial.payout_worker")


class InventoryPayoutWorker:
    def __init__(self, ledger: Any, executor: Any, *, batch_size: int = 100):
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch size must be between 1 and 1000")
        self.ledger, self.executor, self.batch_size = ledger, executor, batch_size
        self._run_lock = threading.Lock()

    def run_once(self) -> dict[str, int]:
        """Process one bounded batch; safe to call again after any interruption."""
        if not self.executor.enabled:
            return {"disabled": 1, "submitted": 0, "finalized": 0, "pending": 0, "errors": 0}
        if not self._run_lock.acquire(blocking=False):
            return {"disabled": 0, "submitted": 0, "finalized": 0, "pending": 0, "errors": 0}
        counts = {"disabled": 0, "submitted": 0, "finalized": 0, "pending": 0, "errors": 0}
        try:
            orders = self.ledger.list_orders(
                states=("deposit_final", "payout_submitted"), limit=self.batch_size
            )
            for order in orders:
                order_id = order["order_id"]
                try:
                    if order["state"] == "deposit_final":
                        self.executor.execute_or_resume(order_id)
                        counts["submitted"] += 1
                    # Re-check every submitted transaction on each cycle. The executor
                    # verifies exact recipient, asset, amount and chain finality.
                    if self.executor.confirm_finalized(order_id):
                        counts["finalized"] += 1
                except PayoutPending:
                    counts["pending"] += 1
                except PayoutError as exc:
                    # Error text is deliberately not logged; adapters may include
                    # provider details that should not enter public/service logs.
                    counts["errors"] += 1
                    LOG.warning("payout held for manual/retry reconciliation (order=%s, error=%s)",
                                order_id, type(exc).__name__)
                except Exception as exc:
                    counts["errors"] += 1
                    LOG.error("unexpected payout worker failure (order=%s, error=%s)",
                              order_id, type(exc).__name__)
            return counts
        finally:
            self._run_lock.release()

    def run_forever(self, stop_event: threading.Event, *, interval_seconds: int = 5) -> None:
        if not 1 <= interval_seconds <= 300:
            raise ValueError("poll interval must be between 1 and 300 seconds")
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(interval_seconds)


def main() -> int:
    config_path = Path(os.environ.get("SOBYA_CUSTODIAL_CONFIG", "config.json")).expanduser()
    ledger_path = Path(os.environ.get("SOBYA_CUSTODIAL_DB", "data/orders.sqlite3")).expanduser()
    journal_path = os.environ.get("SOBYA_PAYOUT_JOURNAL", "data/payout-journal.sqlite3")
    interval = int(os.environ.get("SOBYA_PAYOUT_POLL_SECONDS", "5"))
    if not config_path.is_file():
        raise SystemExit("custodial config file is missing; refusing to start")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    ledger_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger = CustodialOrderLedger(ledger_path)
    executor = build_inventory_payout_executor(config, ledger, journal_path)
    worker = InventoryPayoutWorker(ledger, executor)
    if not executor.enabled:
        LOG.info("custodial payouts are disabled; staying idle without wallet adapters")
    stop = threading.Event()

    def request_stop(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    LOG.info("SOBYA custodial payout worker started; polling every %s seconds", interval)
    try:
        worker.run_forever(stop, interval_seconds=interval)
    finally:
        LOG.info("SOBYA custodial payout worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
