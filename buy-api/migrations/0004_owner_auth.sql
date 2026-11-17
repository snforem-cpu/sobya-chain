-- One-time EIP-191 owner challenges for protected manual-payout actions.
CREATE TABLE IF NOT EXISTS owner_auth_challenges (
  nonce TEXT PRIMARY KEY,
  owner_address TEXT NOT NULL,
  message TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS owner_auth_expiry_idx ON owner_auth_challenges(expires_at);
