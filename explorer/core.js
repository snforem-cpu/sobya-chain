export const CHAIN_ID = 357812033857n;
export const CHAIN_HEX = "0x534f425941";
export const RPC_URL = "https://sobya-evm-rpc.nodesafe-dapp.xyz";
export const HASH_RE = /^0x[0-9a-fA-F]{64}$/;
export const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;
export function classifySearch(value) {
  const q = String(value ?? "").trim();
  if (HASH_RE.test(q)) return { type: "transaction", value: q };
  if (ADDRESS_RE.test(q)) return { type: "address", value: q };
  if (/^(0|[1-9]\d*)$/.test(q)) return { type: "block", value: q };
  throw new TypeError("Enter a valid transaction hash, 0x wallet address, or block number.");
}
export function formatSoby(wei) {
  if (wei == null) return "—";
  const value = BigInt(wei);
  const whole = value / 10n ** 18n;
  const fraction = (value % 10n ** 18n).toString().padStart(18, "0").slice(0, 6).replace(/0+$/, "");
  return whole.toLocaleString("en-US") + (fraction ? "." + fraction : "") + " SOBY";
}
export function shortHash(value, left = 12, right = 10) {
  const s = String(value ?? "");
  return s.length > left + right + 3 ? s.slice(0, left) + "…" + s.slice(-right) : s;
}
export function toDecimal(hex) {
  return hex == null ? "—" : BigInt(hex).toString();
}
