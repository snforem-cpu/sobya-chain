// Pure pricing policy. There is deliberately no upper price ceiling.
// Call this only when applying a newly verified purchase, never on page loads
// or periodic polling. Persist the returned price as the next previousPriceUsd.
export function calculateDynamicPrice({
  referencePriceUsd,
  previousPriceUsd,
  availableInventory,
  initialInventory,
  verifiedDemand24h,
  baselineDemand24h,
  inventoryWeight,
  demandWeight,
  upwardSmoothing,
  downwardSmoothing,
  floorPriceUsd,
}) {
  const values = [
    referencePriceUsd, previousPriceUsd, availableInventory, initialInventory,
    verifiedDemand24h, baselineDemand24h, inventoryWeight, demandWeight,
    upwardSmoothing, downwardSmoothing, floorPriceUsd,
  ];
  if (values.some((v) => !Number.isFinite(v))) throw new TypeError("All pricing inputs must be finite numbers");
  if (referencePriceUsd <= 0 || previousPriceUsd <= 0 || initialInventory <= 0) throw new RangeError("Price and initial inventory must be positive");
  if (availableInventory < 0 || availableInventory > initialInventory) throw new RangeError("Available inventory is outside the configured range");
  if (verifiedDemand24h < 0 || baselineDemand24h < 0) throw new RangeError("Demand values cannot be negative");
  if (inventoryWeight < 0 || demandWeight < 0) throw new RangeError("Pricing weights cannot be negative");
  if (upwardSmoothing <= 0 || upwardSmoothing > 1 || downwardSmoothing <= 0 || downwardSmoothing > 1) throw new RangeError("Smoothing values must be in (0, 1]");
  if (floorPriceUsd <= 0) throw new RangeError("The minimum price must be positive");

  const depletion = 1 - (availableInventory / initialInventory);
  // Positive demand growth is intentionally not capped: strong verified
  // demand can move the target price upward without an artificial ceiling.
  // Demand contraction remains bounded at -100% to keep the target positive.
  const demandDelta = baselineDemand24h === 0
    ? (verifiedDemand24h > 0 ? 1 : 0)
    : Math.max(-1, (verifiedDemand24h - baselineDemand24h) / baselineDemand24h);
  const exponent = inventoryWeight * depletion + demandWeight * demandDelta;
  const target = referencePriceUsd * Math.exp(exponent);
  if (!Number.isFinite(target)) throw new RangeError("Calculated price exceeds the supported numeric range");

  const smoothing = target >= previousPriceUsd ? upwardSmoothing : downwardSmoothing;
  const next = previousPriceUsd + (target - previousPriceUsd) * smoothing;
  if (!Number.isFinite(next)) throw new RangeError("Calculated price exceeds the supported numeric range");
  return Math.max(floorPriceUsd, next);
}
