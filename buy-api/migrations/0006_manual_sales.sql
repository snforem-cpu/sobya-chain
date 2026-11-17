CREATE TABLE IF NOT EXISTS manual_sale_settings (
  id INTEGER PRIMARY KEY CHECK (id=1),
  price_usd REAL NOT NULL CHECK (price_usd>0),
  updated_at INTEGER NOT NULL
);
INSERT OR IGNORE INTO manual_sale_settings (id,price_usd,updated_at) VALUES (1,0.005,unixepoch());

CREATE TABLE IF NOT EXISTS manual_orders (
  id TEXT PRIMARY KEY,
  soby_amount TEXT NOT NULL,
  unit_price_usd REAL NOT NULL,
  total_usd REAL NOT NULL,
  payment_network TEXT NOT NULL,
  payment_asset TEXT NOT NULL,
  payment_amount TEXT NOT NULL,
  payment_tx TEXT NOT NULL,
  buyer_address TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('submitted','under_review','paid_confirmed','completed','rejected')),
  payout_tx TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS manual_orders_created_idx ON manual_orders(created_at DESC);
