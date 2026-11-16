-- Persistent public pricing state. The sale starts with the approved reference
-- price and inventory; production movement parameters remain unset until approved.
CREATE TABLE IF NOT EXISTS pricing_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  reference_price_usd REAL NOT NULL CHECK (reference_price_usd > 0),
  current_price_usd REAL NOT NULL CHECK (current_price_usd > 0),
  initial_inventory_soby REAL NOT NULL CHECK (initial_inventory_soby > 0),
  available_inventory_soby REAL NOT NULL CHECK (
    available_inventory_soby >= 0 AND available_inventory_soby <= initial_inventory_soby
  ),
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pricing_policy (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  baseline_demand_24h REAL,
  inventory_weight REAL,
  demand_weight REAL,
  upward_smoothing REAL,
  downward_smoothing REAL,
  floor_price_usd REAL,
  updated_at INTEGER,
  CHECK (baseline_demand_24h IS NULL OR baseline_demand_24h >= 0),
  CHECK (inventory_weight IS NULL OR inventory_weight >= 0),
  CHECK (demand_weight IS NULL OR demand_weight >= 0),
  CHECK (upward_smoothing IS NULL OR (upward_smoothing > 0 AND upward_smoothing <= 1)),
  CHECK (downward_smoothing IS NULL OR (downward_smoothing > 0 AND downward_smoothing <= 1)),
  CHECK (floor_price_usd IS NULL OR floor_price_usd > 0)
);

INSERT OR IGNORE INTO pricing_state (
  id, reference_price_usd, current_price_usd,
  initial_inventory_soby, available_inventory_soby, updated_at
) VALUES (1, 0.005, 0.005, 1000000, 1000000, unixepoch());

-- Deliberately no pricing_policy seed: weights and smoothing are not yet
-- approved production settings and must not be silently copied from tests.
