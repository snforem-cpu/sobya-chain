-- Add action binding to existing one-time owner challenges.
ALTER TABLE owner_auth_challenges ADD COLUMN action TEXT NOT NULL DEFAULT '';
ALTER TABLE owner_auth_challenges ADD COLUMN context TEXT NOT NULL DEFAULT '';
