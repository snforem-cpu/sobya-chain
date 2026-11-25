CREATE TABLE IF NOT EXISTS exchange_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  current_price_usdt_per_soby TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO exchange_state (id, current_price_usdt_per_soby, updated_at)
VALUES (1, '0.005', strftime('%Y-%m-%dT%H:%M:%fZ','now'));

CREATE TABLE IF NOT EXISTS exchange_quotes (
  order_id TEXT PRIMARY KEY,
  direction TEXT NOT NULL CHECK (direction IN ('buy','return')),
  sender TEXT NOT NULL,
  deposit_address TEXT NOT NULL,
  token_address TEXT,
  chain_id INTEGER NOT NULL,
  requested_amount_atomic TEXT NOT NULL,
  payment_amount_atomic TEXT NOT NULL,
  unique_marker_atomic TEXT NOT NULL,
  payout_amount_atomic TEXT NOT NULL,
  quoted_price TEXT NOT NULL,
  exchange_fee_bps INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  payment_tx_hash TEXT,
  settlement_tx_hash TEXT,
  last_error TEXT,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exchange_quotes_unique_open_payment
  ON exchange_quotes(direction, payment_amount_atomic) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_exchange_quotes_status_expiry
  ON exchange_quotes(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_exchange_quotes_sender
  ON exchange_quotes(sender, created_at);
CREATE TABLE IF NOT EXISTS exchange_replays (
  chain_id INTEGER NOT NULL,
  tx_hash TEXT NOT NULL,
  log_index INTEGER NOT NULL DEFAULT 0,
  order_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(chain_id, tx_hash, log_index)
);
