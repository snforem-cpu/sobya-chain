"""Idempotent order ledger for SOBYA's custodial inventory swap model."""
from __future__ import annotations
import sqlite3, threading, uuid
from pathlib import Path
from typing import Optional

NETWORKS = {"ethereum", "tron", "solana", "sobya"}
DIRECTIONS = {"usdt_to_soby", "soby_to_usdt"}

class CustodialOrderError(ValueError):
    pass

class CustodialOrderLedger:
    """Records one uniquely identified deposit and one payout per swap order."""
    def __init__(self, database: str | Path):
        self.database = str(database)
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS custodial_orders (
                order_id TEXT PRIMARY KEY, direction TEXT NOT NULL,
                source_network TEXT NOT NULL, destination_network TEXT NOT NULL,
                deposit_address TEXT NOT NULL, source_wallet TEXT NOT NULL,
                destination_wallet TEXT NOT NULL, source_asset TEXT NOT NULL,
                destination_asset TEXT NOT NULL, source_amount TEXT NOT NULL,
                destination_amount TEXT NOT NULL, state TEXT NOT NULL,
                deposit_tx TEXT, deposit_event_index INTEGER, payout_tx TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_network, deposit_address),
                UNIQUE(source_network, deposit_tx, deposit_event_index))""")
            db.execute("CREATE INDEX IF NOT EXISTS custodial_orders_state_idx ON custodial_orders(state)")

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        return db

    @staticmethod
    def _required(value, field):
        if not isinstance(value, str) or not value.strip():
            raise CustodialOrderError(f"{field} is required")
        return value.strip()

    def create_order(self, *, direction, source_network, destination_network,
                     deposit_address, source_wallet, destination_wallet,
                     source_asset, destination_asset, source_amount,
                     destination_amount, order_id: Optional[str] = None):
        if direction not in DIRECTIONS:
            raise CustodialOrderError("unsupported swap direction")
        if source_network not in NETWORKS or destination_network not in NETWORKS or source_network == destination_network:
            raise CustodialOrderError("unsupported or identical networks")
        if direction == "usdt_to_soby" and (source_network == "sobya" or destination_network != "sobya"):
            raise CustodialOrderError("USDT-to-SOBY must settle on SOBYA")
        if direction == "soby_to_usdt" and (source_network != "sobya" or destination_network == "sobya"):
            raise CustodialOrderError("SOBY-to-USDT must originate on SOBYA")
        for value in (source_amount, destination_amount):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise CustodialOrderError("amounts must be positive integer base units")
        fields = [self._required(v, n) for v, n in (
            (deposit_address, "deposit address"), (source_wallet, "source wallet"),
            (destination_wallet, "destination wallet"), (source_asset, "source asset"),
            (destination_asset, "destination asset"))]
        oid = order_id or str(uuid.uuid4())
        with self._lock, self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""INSERT INTO custodial_orders
                    (order_id,direction,source_network,destination_network,deposit_address,
                     source_wallet,destination_wallet,source_asset,destination_asset,
                     source_amount,destination_amount,state)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,'created')""",
                    (oid,direction,source_network,destination_network,*fields,
                     str(source_amount),str(destination_amount)))
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise CustodialOrderError("order ID or deposit address already assigned") from exc
        return oid

    def record_deposit(self, order_id, *, tx_id, event_index, observed_amount, observed_recipient, observed_asset):
        tx_id = self._required(tx_id, "deposit transaction ID")
        if not isinstance(event_index, int) or isinstance(event_index, bool) or event_index < 0:
            raise CustodialOrderError("event index must be a non-negative integer")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,deposit_tx,deposit_event_index,deposit_address,source_asset,source_amount FROM custodial_orders WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                db.rollback()
                raise CustodialOrderError("unknown order")
            if not isinstance(observed_amount, int) or isinstance(observed_amount, bool) or observed_amount <= 0:
                db.rollback()
                raise CustodialOrderError("observed deposit amount must be a positive integer")
            if observed_amount != int(row["source_amount"]) or observed_recipient != row["deposit_address"] or observed_asset != row["source_asset"]:
                db.rollback()
                raise CustodialOrderError("deposit amount, recipient, or asset does not match the order")
            if row["deposit_tx"] == tx_id and row["deposit_event_index"] == event_index:
                db.commit()
                return False
            if row["state"] != "created":
                db.rollback()
                raise CustodialOrderError("order is not awaiting a deposit")
            try:
                db.execute("""UPDATE custodial_orders SET state='deposit_seen',deposit_tx=?,
                    deposit_event_index=?,updated_at=CURRENT_TIMESTAMP WHERE order_id=?""",
                    (tx_id,event_index,order_id))
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise CustodialOrderError("deposit event already assigned to another order") from exc
        return True

    def confirm_deposit_final(self, order_id, *, verified):
        if verified is not True:
            raise CustodialOrderError("deposit requires positive finalized-chain verification")
        self._transition(order_id, "deposit_seen", "deposit_final")

    def submit_payout(self, order_id, *, payout_tx):
        payout_tx = self._required(payout_tx, "payout transaction ID")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,payout_tx FROM custodial_orders WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                db.rollback()
                raise CustodialOrderError("unknown order")
            if row["state"] == "payout_submitted" and row["payout_tx"] == payout_tx:
                db.commit()
                return
            if row["state"] != "deposit_final":
                db.rollback()
                raise CustodialOrderError("payout allowed only after finalized deposit")
            db.execute("""UPDATE custodial_orders SET state='payout_submitted',payout_tx=?,
                updated_at=CURRENT_TIMESTAMP WHERE order_id=?""", (payout_tx,order_id))
            db.commit()

    def confirm_payout_final(self, order_id, *, verified, observed_amount, observed_recipient, observed_asset):
        if verified is not True:
            raise CustodialOrderError("payout requires positive finalized-chain verification")
        row = self.get_order(order_id)
        if row is None:
            raise CustodialOrderError("unknown order")
        if (not isinstance(observed_amount, int) or isinstance(observed_amount, bool)
                or observed_amount != int(row["destination_amount"])
                or observed_recipient != row["destination_wallet"]
                or observed_asset != row["destination_asset"]):
            raise CustodialOrderError("payout amount, recipient, or asset does not match the order")
        self._transition(order_id, "payout_submitted", "complete")

    def reject(self, order_id):
        self._transition(order_id, "created", "rejected")

    def _transition(self, order_id, expected, target):
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute("""UPDATE custodial_orders SET state=?,updated_at=CURRENT_TIMESTAMP
                WHERE order_id=? AND state=?""", (target,order_id,expected))
            if cur.rowcount != 1:
                db.rollback()
                raise CustodialOrderError(f"order must be in {expected} state")
            db.commit()

    def get_order(self, order_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM custodial_orders WHERE order_id=?", (order_id,)).fetchone()
            return dict(row) if row else None
