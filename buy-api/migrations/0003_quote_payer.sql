-- Store the payer separately from the wallet that receives SOBY.
-- For Solana this is a base58 public key; for EVM it is a 0x address.
ALTER TABLE quotes ADD COLUMN payer_address TEXT;
