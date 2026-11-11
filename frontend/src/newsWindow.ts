import type { NewsItem } from "./api/stocks";

const DAY_MS = 86_400_000;
// The news list grows two weeks at a time.
export const NEWS_WINDOW_MS = 14 * DAY_MS;

export interface SkippedStretch {
  from: Date;
  to: Date;
}

export function firstCutoff(now: Date): Date {
  return new Date(now.getTime() - NEWS_WINDOW_MS);
}

/**
 * The next cutoff after "Show more": the 2-week stretch holding the next older news item,
 * skipping (and reporting) empty stretches in between. Null when nothing older is left.
 */
export function showMore(
  items: NewsItem[],
  now: Date,
  cutoff: Date,
): { cutoff: Date; skipped: SkippedStretch | null } | null {
  const older = items.map((item) => Date.parse(item.time)).filter((instant) => instant < cutoff.getTime());
  if (older.length === 0) return null;
  const newestOlder = Math.max(...older);
  const stretch = Math.floor((now.getTime() - newestOlder) / NEWS_WINDOW_MS);
  const stretchStart = new Date(now.getTime() - stretch * NEWS_WINDOW_MS);
  const isNextStretch = stretchStart.getTime() >= cutoff.getTime();
  return {
    cutoff: new Date(now.getTime() - (stretch + 1) * NEWS_WINDOW_MS),
    skipped: isNextStretch ? null : { from: stretchStart, to: cutoff },
  };
}
