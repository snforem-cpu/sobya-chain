-- Permanent, atomic replay protection for SOBYA Tokenomics Studio licenses.
-- Unique indexes are enforced by SQLite/D1, including simultaneous requests.
CREATE TABLE IF NOT EXISTS license_issuance_reservations (
  transaction_hash TEXT PRIMARY KEY CHECK (length(transaction_hash) = 66),
  license_id TEXT NOT NULL UNIQUE CHECK (length(license_id) BETWEEN 1 AND 80),
  created_at INTEGER NOT NULL
);
