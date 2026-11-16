import { useEffect } from "react";
import type { JournalPeriod } from "./api/journal";
import type { RunningScan } from "./api/setups";
import type { Quote } from "./api/stocks";
import { formatSignedDollars } from "./format";

// Chrome's tab strip and hover card show the title from the start, so each one leads with
// what tells that tab apart (the ticker, the screen, the scan) and ends with the app name.
const APP_NAME = "Finviz";
const SEPARATOR = " · ";
const MINUS_SIGN = "−";

const PERIOD_WORDS: Record<JournalPeriod, string> = {
  today: "today",
  week: "this week",
  month: "this month",
  all: "all time",
};

function title(...parts: string[]): string {
  return [...parts, APP_NAME].join(SEPARATOR);
}

// Finviz sends change as "12.30%" or "-0.57%".
function signedChange(change: string): string {
  if (change.startsWith("-")) return `${MINUS_SIGN}${change.slice(1)}`;
  return change.startsWith("+") || Number.parseFloat(change) === 0 ? change : `+${change}`;
}

export function stockTitle(ticker: string | null, quote: Quote | null): string {
  if (!ticker) return title("Stock");
  const price = quote?.Price;
  const change = quote?.Change;
  if (!price || !change) return title(ticker);
  return title(`${ticker} ${price} ${signedChange(change)}`);
}

export function setupsTitle(setupCount: number | null, scan: RunningScan | null): string {
  if (scan) return title(scan.phase === "scanning" ? `Scanning ${scan.done}/${scan.total}` : "Scanning…");
  return setupCount == null ? title("Setups") : title("Setups", String(setupCount));
}

export function screensTitle(screenName: string | null): string {
  return screenName ? title("Screens", screenName) : title("Screens");
}

export function watchlistTitle(stockCount: number | null): string {
  return stockCount == null ? title("Watchlist") : title("Watchlist", `${stockCount} stocks`);
}

export function journalTitle(netPnl: number | null, period: JournalPeriod): string {
  return netPnl == null ? title("Journal") : title("Journal", `${formatSignedDollars(netPnl)} ${PERIOD_WORDS[period]}`);
}

export function trackRecordTitle(): string {
  return title("Track record");
}

export function useDocumentTitle(pageTitle: string): void {
  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);
}
