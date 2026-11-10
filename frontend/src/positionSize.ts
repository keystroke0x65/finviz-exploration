// Prices like 1.84 - 1.76 come out as 0.0800000001; without this, 50 / 0.08 floors to 624.
const FLOAT_TOLERANCE = 1e-9;

// Shares that lose `riskPerTrade` dollars if the stop is hit, capped by the largest position allowed.
export function suggestShares(riskPerTrade: number, entry: number, stop: number, maxPosition: number | null): number {
  const riskPerShare = Math.abs(entry - stop);
  if (riskPerShare === 0 || entry <= 0) return 0;
  const byRisk = Math.floor(riskPerTrade / riskPerShare + FLOAT_TOLERANCE);
  if (maxPosition == null) return byRisk;
  return Math.min(byRisk, Math.floor(maxPosition / entry + FLOAT_TOLERANCE));
}
