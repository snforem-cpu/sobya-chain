import { AUTO_EXCHANGE_POLICY } from "./config.js";

const PRICE_SCALE = 10n ** 18n;
const SOBY_SCALE = 10n ** 18n;

export function parsePriceAtomic(value) {
  const s = String(value ?? "").trim();
  if (!/^\d+(?:\.\d{1,18})?$/.test(s)) throw new TypeError("price must have up to 18 decimal places");
  const [whole, fraction = ""] = s.split(".");
  const result = BigInt(whole) * PRICE_SCALE + BigInt((fraction + "0".repeat(18)).slice(0, 18));
  if (result <= 0n) throw new TypeError("price must be positive");
  return result;
}

export function formatPriceAtomic(value) {
  const n = BigInt(value);
  return String(n / PRICE_SCALE) + "." + String(n % PRICE_SCALE).padStart(18, "0").replace(/0+$/, "");
}

/**
 * Applies the agreed inventory-relative price movement.
 * quantitySobyAtomic is the confirmed quantity sold (up) or returned (down).
 * The caller must invoke this only after a confirmed, successfully settled trade.
 */
export function calculateNextPrice({ currentPrice, quantitySobyAtomic, direction }) {
  const price = typeof currentPrice === "bigint" ? currentPrice : parsePriceAtomic(currentPrice);
  const quantity = BigInt(quantitySobyAtomic);
  if (price <= 0n || quantity <= 0n) throw new TypeError("price and quantity must be positive");
  if (direction !== "up" && direction !== "down") throw new TypeError('direction must be "up" or "down"');

  const coefficient = BigInt(direction === "up"
    ? AUTO_EXCHANGE_POLICY.upwardPriceCoefficient
    : AUTO_EXCHANGE_POLICY.downwardPriceCoefficient);
  const denominator = BigInt(AUTO_EXCHANGE_POLICY.priceImpactDenominator) *
    BigInt(AUTO_EXCHANGE_POLICY.referenceInventorySoby) * SOBY_SCALE;
  const adjustment = coefficient * quantity;
  const numerator = direction === "up"
    ? denominator + adjustment
    : denominator - adjustment;
  if (numerator <= 0n) throw new RangeError("inventory return would reduce price to zero or below");
  return price * numerator / denominator;
}

export function applyConfirmedPriceChange({ ledger, quantitySobyAtomic, direction, settlementConfirmed }) {
  if (!ledger || !Array.isArray(ledger.quotes)) throw new TypeError("ledger.quotes must be an array");
  if (settlementConfirmed !== true) throw new Error("price can change only after confirmed settlement");
  const currentPrice = ledger.currentPriceUsdtPerSoby ?? AUTO_EXCHANGE_POLICY.openingPriceUsdtPerSoby;
  const nextPriceAtomic = calculateNextPrice({ currentPrice, quantitySobyAtomic, direction });
  return {
    ...ledger,
    currentPriceUsdtPerSoby: formatPriceAtomic(nextPriceAtomic),
    lastPriceChange: {
      direction,
      quantitySobyAtomic: BigInt(quantitySobyAtomic).toString(),
      previousPrice: String(currentPrice),
      newPrice: formatPriceAtomic(nextPriceAtomic)
    }
  };
}
