export const MISSING_VALUE = "—";

export function formatNumber(value: number | null, decimals = 2): string {
  return value == null ? MISSING_VALUE : value.toFixed(decimals);
}

export function formatPercent(value: number | null): string {
  return value == null ? MISSING_VALUE : `${value.toFixed(2)}%`;
}

export function formatCount(value: number | null): string {
  return value == null ? MISSING_VALUE : value.toLocaleString("en-US");
}

export function finvizQuoteUrl(ticker: string): string {
  return `https://finviz.com/quote.ashx?t=${encodeURIComponent(ticker)}`;
}

// News URLs come from Finviz; only link out to plain web pages so a
// `javascript:` or other scheme can never run in the app.
export function isWebUrl(url: string | null): url is string {
  if (!url) {
    return false;
  }
  try {
    const protocol = new URL(url).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

// Market days are New York calendar days, matching how the backend records
// watchlist appearances.
export function formatEasternDate(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleDateString("en-CA", { timeZone: "America/New_York" });
}

export function formatSignedPercent(value: number | null): string {
  if (value == null) {
    return MISSING_VALUE;
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function changeClass(value: number | null): string {
  if (value == null || value === 0) {
    return "";
  }
  return value > 0 ? "gain" : "loss";
}
