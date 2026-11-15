// Pure pricing policy. Parameters are deliberately supplied by the caller;
// no unapproved production caps or movement rates are silently hard-coded.
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
  ceilingPriceUsd,
}) {
  const values = [
    referencePriceUsd, previousPriceUsd, availableInventory, initialInventory,
    verifiedDemand24h, baselineDemand24h, inventoryWeight, demandWeight,
    upwardSmoothing, downwardSmoothing, floorPriceUsd, ceilingPriceUsd,
  ];
  if (values.some((v) => !Number.isFinite(v))) throw new TypeError("All pricing inputs must be finite numbers");
  if (referencePriceUsd <= 0 || previousPriceUsd <= 0 || initialInventory <= 0) throw new RangeError("Price and initial inventory must be positive");
  if (availableInventory < 0 || availableInventory > initialInventory) throw new RangeError("Available inventory is outside the configured range");
  if (verifiedDemand24h < 0 || baselineDemand24h < 0) throw new RangeError("Demand values cannot be negative");
  if (inventoryWeight < 0 || demandWeight < 0) throw new RangeError("Pricing weights cannot be negative");
  if (upwardSmoothing <= 0 || upwardSmoothing > 1 || downwardSmoothing <= 0 || downwardSmoothing > 1) throw new RangeError("Smoothing values must be in (0, 1]");
  if (floorPriceUsd <= 0 || ceilingPriceUsd < floorPriceUsd) throw new RangeError("Invalid price bounds");

  const depletion = 1 - (availableInventory / initialInventory);
  const demandDelta = baselineDemand24h === 0
    ? (verifiedDemand24h > 0 ? 1 : 0)
    : Math.max(-1, Math.min(1, (verifiedDemand24h - baselineDemand24h) / baselineDemand24h));
  const target = referencePriceUsd * (1 + inventoryWeight * depletion + demandWeight * demandDelta);
  const boundedTarget = Math.max(floorPriceUsd, Math.min(ceilingPriceUsd, target));
  const smoothing = boundedTarget >= previousPriceUsd ? upwardSmoothing : downwardSmoothing;
  const next = previousPriceUsd + (boundedTarget - previousPriceUsd) * smoothing;
  return Math.max(floorPriceUsd, Math.min(ceilingPriceUsd, next));
}
