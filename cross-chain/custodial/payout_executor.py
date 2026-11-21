"""Durable, idempotent payout orchestration for the shared inventory model.

Signed transactions are persisted before broadcast. A retry rebroadcasts the exact
same signed payload; it never allocates a second nonce or creates a second payment.
Chain-specific adapters must implement prepare/broadcast/verify_finalized.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import stat
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class PayoutError(RuntimeError):
    pass


class PayoutPending(PayoutError):
    """The payout is safely recorded but not yet finalized."""


@dataclass(frozen=True)
class PayoutIntent:
    order_id: str
    network: str
    asset: str
    amount_base_units: int
    destination: str


@dataclass(frozen=True)
class PreparedPayout:
    tx_id: str
    signed_payload: bytes


class PayoutAdapter(Protocol):
    network: str
    def prepare(self, intent: PayoutIntent) -> PreparedPayout: ...
    def broadcast(self, prepared: PreparedPayout) -> str: ...
    def verify_finalized(self, intent: PayoutIntent, tx_id: str) -> bool: ...


class PayoutJournal:
    """Private SQLite journal; signed payloads are sensitive and never logged."""
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.exists():
            info = self.path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise PayoutError("payout journal must be a regular non-symlink file")
            if info.st_mode & 0o077:
                raise PayoutError("payout journal permissions must be owner-only (0600)")
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS payout_journal (
                order_id TEXT PRIMARY KEY,
                network TEXT NOT NULL,
                asset TEXT NOT NULL,
                amount_base_units TEXT NOT NULL,
                destination TEXT NOT NULL,
                tx_id TEXT NOT NULL UNIQUE,
                signed_payload_b64 TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('prepared','broadcast','finalized','failed')),
                last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
        os.chmod(self.path, 0o600)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        return db

    def get(self, order_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM payout_journal WHERE order_id=?", (order_id,)).fetchone()
            return dict(row) if row else None

    def create_prepared(self, intent: PayoutIntent, prepared: PreparedPayout):
        if not prepared.tx_id or not prepared.signed_payload:
            raise PayoutError("adapter returned an empty signed transaction")
        encoded = base64.b64encode(prepared.signed_payload).decode("ascii")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM payout_journal WHERE order_id=?", (intent.order_id,)).fetchone()
            if row:
                db.rollback()
                if (row["network"], row["asset"], row["amount_base_units"], row["destination"]) != (
                    intent.network, intent.asset, str(intent.amount_base_units), intent.destination
                ):
                    raise PayoutError("order already has a different immutable payout intent")
                return dict(row)
            try:
                db.execute("""INSERT INTO payout_journal
                    (order_id,network,asset,amount_base_units,destination,tx_id,
                     signed_payload_b64,state)
                    VALUES (?,?,?,?,?,?,?,'prepared')""",
                    (intent.order_id,intent.network,intent.asset,str(intent.amount_base_units),
                     intent.destination,prepared.tx_id,encoded))
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise PayoutError("transaction ID or order already exists in payout journal") from exc
        return self.get(intent.order_id)

    @staticmethod
    def prepared_from_row(row: dict[str, Any]) -> PreparedPayout:
        return PreparedPayout(row["tx_id"], base64.b64decode(row["signed_payload_b64"], validate=True))

    def mark(self, order_id: str, state: str, error: str | None = None):
        if state not in {"broadcast","finalized","failed"}:
            raise PayoutError("invalid payout journal state")
        # Error messages are intentionally generic; never persist RPC payloads or secrets.
        safe_error = (error or "")[:180] if state == "failed" else None
        with self._connect() as db:
            db.execute("UPDATE payout_journal SET state=?,last_error=?,updated_at=CURRENT_TIMESTAMP WHERE order_id=?",
                       (state,safe_error,order_id))


class InventoryPayoutExecutor:
    """Coordinates an immutable order, a chain adapter, and durable retry journal."""
    def __init__(self, ledger: Any, journal: PayoutJournal, adapters: dict[str, PayoutAdapter]):
        self.ledger, self.journal = ledger, journal
        self.adapters = {k.lower(): v for k,v in adapters.items()}
        self._lock = threading.RLock()

    def _intent(self, order_id: str) -> tuple[dict[str, Any], PayoutIntent, PayoutAdapter]:
        order = self.ledger.get_order(order_id)
        if not order:
            raise PayoutError("unknown order")
        if order.get("state") not in {"deposit_final","payout_submitted","complete"}:
            raise PayoutError("payout is allowed only after a finalized deposit")
        network = str(order.get("destination_network","")).lower()
        adapter = self.adapters.get(network)
        if adapter is None or adapter.network.lower() != network:
            raise PayoutError("destination payout adapter is not configured")
        amount = int(order["destination_amount"])
        if amount <= 0:
            raise PayoutError("payout amount must be positive base units")
        intent = PayoutIntent(order_id,network,order["destination_asset"],amount,order["destination_wallet"])
        return order,intent,adapter

    def execute_or_resume(self, order_id: str) -> str:
        """Prepare once, persist signed bytes, then broadcast the same tx on every retry."""
        with self._lock:
            order,intent,adapter = self._intent(order_id)
            row = self.journal.get(order_id)
            if row is None:
                prepared = adapter.prepare(intent)
                row = self.journal.create_prepared(intent,prepared)
            else:
                if (row["network"],row["asset"],row["amount_base_units"],row["destination"]) != (
                    intent.network,intent.asset,str(intent.amount_base_units),intent.destination
                ):
                    raise PayoutError("journal does not match the immutable order")
            if row["state"] == "finalized":
                return row["tx_id"]
            prepared = self.journal.prepared_from_row(row)
            try:
                observed_tx = adapter.broadcast(prepared)
            except Exception as exc:
                # Keep 'prepared'; retry can only rebroadcast the same signed bytes.
                raise PayoutPending("broadcast outcome is uncertain; retry will rebroadcast the same transaction") from exc
            if observed_tx.lower() != prepared.tx_id.lower():
                raise PayoutError("RPC returned a transaction ID different from the signed transaction")
            self.journal.mark(order_id,"broadcast")
            current = self.ledger.get_order(order_id)
            if current["state"] == "deposit_final":
                self.ledger.submit_payout(order_id,payout_tx=prepared.tx_id)
            elif current["state"] == "payout_submitted" and current.get("payout_tx","").lower() != prepared.tx_id.lower():
                raise PayoutError("ledger payout transaction conflicts with durable journal")
            return prepared.tx_id

    def confirm_finalized(self, order_id: str) -> bool:
        with self._lock:
            order,intent,adapter = self._intent(order_id)
            row = self.journal.get(order_id)
            if not row or row["state"] not in {"broadcast","finalized"}:
                raise PayoutError("no broadcast payout is available for finality verification")
            if order["state"] == "complete":
                if row["state"] != "finalized":
                    self.journal.mark(order_id,"finalized")
                return True
            if order["state"] != "payout_submitted" or order.get("payout_tx","").lower() != row["tx_id"].lower():
                raise PayoutError("ledger and payout journal do not agree")
            if adapter.verify_finalized(intent,row["tx_id"]) is not True:
                raise PayoutPending("payout is not yet finalized with the exact amount and recipient")
            self.ledger.confirm_payout_final(
                order_id,verified=True,observed_amount=intent.amount_base_units,
                observed_recipient=intent.destination,observed_asset=intent.asset
            )
            self.journal.mark(order_id,"finalized")
            return True
