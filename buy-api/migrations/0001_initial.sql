PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS inventory_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  wallet_address TEXT NOT NULL,
  initial_inventory_wei TEXT NOT NULL,
  available_inventory_wei TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quotes (
  id TEXT PRIMARY KEY,
  buyer_address TEXT NOT NULL,
  soby_amount_wei TEXT NOT NULL,
  price_usd_micros INTEGER NOT NULL,
  total_usd_micros INTEGER NOT NULL,
  payment_asset TEXT NOT NULL,
  payment_chain_id INTEGER NOT NULL,
  payment_amount_base_units TEXT,
  expires_at INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('issued','expired','paid','cancelled')),
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS quotes_expiry_idx ON quotes(status, expires_at);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  quote_id TEXT NOT NULL UNIQUE REFERENCES quotes(id),
  buyer_address TEXT NOT NULL,
  payment_chain_id INTEGER NOT NULL,
  payment_tx_hash TEXT,
  payment_amount_base_units TEXT,
  payment_asset TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('awaiting_payment','confirming','verified','payout_pending','paid','failed','refunded')),
  payout_tx_hash TEXT,
  failure_code TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS orders_payment_tx_unique
ON orders(payment_chain_id, payment_tx_hash)
WHERE payment_tx_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT,
  event_type TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
