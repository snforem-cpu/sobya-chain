import { verifyMessage } from "viem";

export const OWNER_WALLET = "0xebdb899fFE84a89e1d576964b640491c135651AD";

export async function issueOwnerChallenge(db, address) {
  if (!db) throw new Error("database_not_configured");
  if (typeof address !== "string" || address.toLowerCase() !== OWNER_WALLET.toLowerCase()) {
    throw new Error("owner_wallet_required");
  }
  const nonce = crypto.randomUUID();
  const now = Math.floor(Date.now() / 1000);
  const expiresAt = now + 300;
  const message = [
    "SOBYA BUY OWNER AUTHORIZATION",
    "Action: one-time dashboard request",
    "Wallet: " + OWNER_WALLET,
    "Nonce: " + nonce,
    "Issued At: " + now,
    "Expires At: " + expiresAt,
    "Do not sign this message if you did not initiate a SOBYA BUY admin action."
  ].join("\n");
  await db.prepare(
    "INSERT INTO owner_auth_challenges (nonce,owner_address,message,expires_at,created_at) VALUES (?,?,?,?,?)"
  ).bind(nonce, OWNER_WALLET.toLowerCase(), message, expiresAt, now).run();
  return { nonce, message, expiresAt };
}

export async function consumeOwnerChallenge(db, auth) {
  if (!db || !auth || typeof auth.nonce !== "string" || typeof auth.signature !== "string" ||
      typeof auth.address !== "string" || auth.address.toLowerCase() !== OWNER_WALLET.toLowerCase()) {
    throw new Error("owner_auth_required");
  }
  const row = await db.prepare(
    "SELECT * FROM owner_auth_challenges WHERE nonce=? AND owner_address=?"
  ).bind(auth.nonce, OWNER_WALLET.toLowerCase()).first();
  const now = Math.floor(Date.now() / 1000);
  if (!row || row.expires_at < now) throw new Error("owner_challenge_expired");
  const valid = await verifyMessage({
    address: OWNER_WALLET,
    message: row.message,
    signature: auth.signature
  }).catch(() => false);
  if (!valid) throw new Error("owner_signature_invalid");
  const consumed = await db.prepare(
    "DELETE FROM owner_auth_challenges WHERE nonce=? AND expires_at>=?"
  ).bind(auth.nonce, now).run();
  if (!consumed.meta?.changes) throw new Error("owner_challenge_already_used");
  return OWNER_WALLET;
}
