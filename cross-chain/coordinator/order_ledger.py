"""Durable SQLite coordination ledger for cross-chain swap evidence.

This ledger records already-verified evidence. It does not verify signatures,
query chains, sign attestations, submit transactions, or release funds.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import time
from typing import Any


class LedgerError(ValueError):
    pass


@dataclass(frozen=True)
class OrderQuote:
    order_id: str
    source_chain: str
    source_asset: str
    source_amount: int
    user: str
    solver: str
    destination_chain_id: int
    destination_recipient: str
    destination_amount: int
    quote_expiry: int
    refund_after: int


@dataclass(frozen=True)
class SourceDepositEvidence:
    order_id: str
    source_chain: str
    transaction_id: str
    event_index: int
    source_asset: str
    source_amount: int
    user: str
    solver: str
    destination_chain_id: int
    destination_recipient: str
    destination_amount: int
    finalized_reference: str


@dataclass(frozen=True)
class DestinationPayoutEvidence:
    order_id: str
    transaction_id: str
    event_index: int
    destination_chain_id: int
    source_chain: str
    source_asset: str
    source_amount: int
    recipient: str
    destination_amount: int
    solver: str
    finalized_reference: str


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


class CrossChainOrderLedger:
    """SQLite-backed monotonic evidence ledger with replay-resistant uniqueness."""

    def __init__(self, database_path: str):
        self.db = sqlite3.connect(database_path, timeout=15, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                quote_json TEXT NOT NULL,
                quote_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('QUOTED','SOURCE_FUNDED','DESTINATION_PAID')),
                source_chain TEXT NOT NULL,
                source_tx TEXT,
                source_event_index INTEGER,
                source_evidence_digest TEXT,
                destination_tx TEXT,
                destination_event_index INTEGER,
                destination_evidence_digest TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                CHECK (
                    (status = 'QUOTED' AND source_tx IS NULL AND destination_tx IS NULL)
                    OR (status = 'SOURCE_FUNDED' AND source_tx IS NOT NULL AND destination_tx IS NULL)
                    OR (status = 'DESTINATION_PAID' AND source_tx IS NOT NULL AND destination_tx IS NOT NULL)
                )
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_source_event
                ON orders(source_chain, source_tx, source_event_index)
                WHERE source_tx IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS uq_destination_event
                ON orders(destination_tx, destination_event_index)
                WHERE destination_tx IS NOT NULL;
            CREATE TABLE IF NOT EXISTS ledger_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL REFERENCES orders(order_id),
                event_type TEXT NOT NULL,
                evidence_digest TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(order_id, event_type),
                UNIQUE(evidence_digest)
            );
        """)

    def register_quote(self, quote: OrderQuote, now: int | None = None) -> None:
        now = int(time.time()) if now is None else now
        if (not quote.order_id or not quote.source_chain or not quote.source_asset
            or not quote.user or not quote.solver or not quote.destination_recipient
            or min(quote.source_amount, quote.destination_amount, quote.destination_chain_id) <= 0
            or quote.quote_expiry <= now or quote.refund_after <= quote.quote_expiry):
            raise LedgerError("invalid or expired signed quote")
        payload = {
            "order_id": quote.order_id, "source_chain": quote.source_chain,
            "source_asset": quote.source_asset, "source_amount": quote.source_amount,
            "user": quote.user, "solver": quote.solver,
            "destination_chain_id": quote.destination_chain_id,
            "destination_recipient": quote.destination_recipient,
            "destination_amount": quote.destination_amount,
            "quote_expiry": quote.quote_expiry, "refund_after": quote.refund_after,
        }
        digest = _digest(payload)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """INSERT INTO orders(order_id,quote_json,quote_digest,status,source_chain,created_at,updated_at)
                   VALUES(?,?,?,'QUOTED',?,?,?)""",
                (quote.order_id, _canonical(payload), digest, quote.source_chain, now, now),
            )
            self.db.execute(
                "INSERT INTO ledger_events(order_id,event_type,evidence_digest,created_at) VALUES(?,?,?,?)",
                (quote.order_id, "QUOTE_REGISTERED", digest, now),
            )
            self.db.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            self.db.execute("ROLLBACK")
            raise LedgerError("order quote already registered or replayed") from exc
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def record_source_deposit(self, evidence: SourceDepositEvidence,
                              now: int | None = None) -> None:
        now = int(time.time()) if now is None else now
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._order(evidence.order_id)
            if row["status"] != "QUOTED":
                raise LedgerError("source deposit already recorded or order is not quote-pending")
            quote = json.loads(row["quote_json"])
            fields = {
                "source_chain": evidence.source_chain,
                "source_asset": evidence.source_asset,
                "source_amount": evidence.source_amount,
                "user": evidence.user,
                "solver": evidence.solver,
                "destination_chain_id": evidence.destination_chain_id,
                "destination_recipient": evidence.destination_recipient,
                "destination_amount": evidence.destination_amount,
            }
            for key, actual in fields.items():
                if quote[key] != actual:
                    raise LedgerError(f"verified source deposit does not match quote: {key}")
            if not evidence.transaction_id or evidence.event_index < 0 or not evidence.finalized_reference:
                raise LedgerError("source deposit evidence is incomplete")
            digest = _digest(evidence.__dict__)
            self.db.execute(
                """UPDATE orders SET status='SOURCE_FUNDED',source_tx=?,source_event_index=?,
                   source_evidence_digest=?,updated_at=? WHERE order_id=?""",
                (evidence.transaction_id, evidence.event_index, digest, now, evidence.order_id),
            )
            self.db.execute(
                "INSERT INTO ledger_events(order_id,event_type,evidence_digest,created_at) VALUES(?,?,?,?)",
                (evidence.order_id, "SOURCE_DEPOSIT_VERIFIED", digest, now),
            )
            self.db.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            self.db.execute("ROLLBACK")
            raise LedgerError("source transaction/event replay detected") from exc
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def record_destination_payout(self, evidence: DestinationPayoutEvidence,
                                  now: int | None = None) -> None:
        now = int(time.time()) if now is None else now
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._order(evidence.order_id)
            if row["status"] != "SOURCE_FUNDED":
                raise LedgerError("destination payout requires a verified source deposit")
            quote = json.loads(row["quote_json"])
            fields = {
                "source_chain": evidence.source_chain,
                "source_asset": evidence.source_asset,
                "source_amount": evidence.source_amount,
                "destination_chain_id": evidence.destination_chain_id,
                "recipient": evidence.recipient,
                "destination_amount": evidence.destination_amount,
                "solver": evidence.solver,
            }
            expected = {
                "source_chain": quote["source_chain"], "source_asset": quote["source_asset"],
                "source_amount": quote["source_amount"],
                "destination_chain_id": quote["destination_chain_id"],
                "recipient": quote["destination_recipient"],
                "destination_amount": quote["destination_amount"], "solver": quote["solver"],
            }
            for key, actual in fields.items():
                if expected[key] != actual:
                    raise LedgerError(f"destination payout does not match quote: {key}")
            if not evidence.transaction_id or evidence.event_index < 0 or not evidence.finalized_reference:
                raise LedgerError("destination payout evidence is incomplete")
            digest = _digest(evidence.__dict__)
            self.db.execute(
                """UPDATE orders SET status='DESTINATION_PAID',destination_tx=?,
                   destination_event_index=?,destination_evidence_digest=?,updated_at=?
                   WHERE order_id=?""",
                (evidence.transaction_id, evidence.event_index, digest, now, evidence.order_id),
            )
            self.db.execute(
                "INSERT INTO ledger_events(order_id,event_type,evidence_digest,created_at) VALUES(?,?,?,?)",
                (evidence.order_id, "DESTINATION_PAYOUT_VERIFIED", digest, now),
            )
            self.db.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            self.db.execute("ROLLBACK")
            raise LedgerError("destination transaction/event replay detected") from exc
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def get_order(self, order_id: str) -> dict[str, Any]:
        row = self._order(order_id)
        result = dict(row)
        result["quote"] = json.loads(result.pop("quote_json"))
        result["events"] = [dict(event) for event in self.db.execute(
            "SELECT event_type,evidence_digest,created_at FROM ledger_events WHERE order_id=? ORDER BY sequence",
            (order_id,),
        )]
        return result

    def _order(self, order_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if row is None:
            raise LedgerError("unknown order ID")
        return row

    def close(self) -> None:
        self.db.close()
