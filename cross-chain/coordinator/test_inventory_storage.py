import sqlite3
import tempfile
import unittest
from pathlib import Path

from order_ledger import CrossChainOrderLedger


class InventoryStorageTests(unittest.TestCase):
    def test_migrates_legacy_integer_inventory_without_losing_reservations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "legacy.sqlite")
            db = sqlite3.connect(path)
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("""
                CREATE TABLE orders(
                    order_id TEXT PRIMARY KEY, quote_json TEXT, quote_digest TEXT,
                    status TEXT, source_chain TEXT, source_tx TEXT,
                    source_event_index INTEGER, source_evidence_digest TEXT,
                    destination_tx TEXT, destination_event_index INTEGER,
                    destination_evidence_digest TEXT, created_at INTEGER, updated_at INTEGER
                )
            """)
            db.execute("""
                CREATE TABLE solver_inventory(
                    solver TEXT PRIMARY KEY,
                    total_units INTEGER NOT NULL,
                    reserved_units INTEGER NOT NULL DEFAULT 0
                )
            """)
            db.execute("""
                CREATE TABLE inventory_reservations(
                    order_id TEXT PRIMARY KEY REFERENCES orders(order_id),
                    solver TEXT NOT NULL REFERENCES solver_inventory(solver),
                    units INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            db.execute("INSERT INTO orders(order_id) VALUES('legacy-order')")
            db.execute("INSERT INTO solver_inventory VALUES(?,?,?)",
                       ("solver", 9_000_000_000_000_000_000, 1_000_000_000_000_000_000))
            db.execute("INSERT INTO inventory_reservations VALUES(?,?,?,?,?,?)",
                       ("legacy-order", "solver", 1_000_000_000_000_000_000,
                        "ACTIVE", 1, 1))
            db.commit()
            db.close()

            ledger = CrossChainOrderLedger(path)
            try:
                self.assertEqual(
                    ledger.available_solver_inventory("solver"),
                    8_000_000_000_000_000_000,
                )
                columns = {
                    row["name"]: row["type"].upper()
                    for row in ledger.db.execute("PRAGMA table_info(solver_inventory)")
                }
                self.assertEqual(columns["total_units"], "TEXT")
                reservation = ledger.db.execute(
                    "SELECT units,status FROM inventory_reservations WHERE order_id='legacy-order'"
                ).fetchone()
                self.assertEqual(reservation["units"], "1000000000000000000")
                self.assertEqual(reservation["status"], "ACTIVE")
                self.assertEqual(list(ledger.db.execute("PRAGMA foreign_key_check")), [])
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
