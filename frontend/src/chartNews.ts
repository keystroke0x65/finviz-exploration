import type { Bar } from "./api/bars";
import type { NewsItem } from "./api/stocks";
import { toChartTime } from "./chartTime";
import { easternParts } from "./easternTime";

interface PlacedBar {
  chartTime: number;
  instant: number;
  day: string;
}

function placeBars(bars: Bar[]): PlacedBar[] {
  return bars
    .map((bar) => ({ chartTime: toChartTime(bar.time), instant: Date.parse(bar.time), day: easternParts(bar.time).date }))
    .sort((left, right) => left.instant - right.instant);
}

// Index of the last bar at or before `instant`, or -1.
function lastBarAtOrBefore(placed: PlacedBar[], instant: number): number {
  let low = 0;
  let high = placed.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (placed[middle].instant <= instant) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

/**
 * The chart bar each news item belongs on, keyed by chart time.
 *
 * News goes on the bar it came out in (the last bar that day at or before it). News from
 * before a day's first bar (overnight, or a weekend on a daily chart) goes on the next bar.
 * News from before the chart's first day or after its last bar has no bar.
 */
export function newsByBarTime(news: NewsItem[], bars: Bar[]): Map<number, NewsItem[]> {
  const placed = placeBars(bars);
  const grouped = new Map<number, NewsItem[]>();
  if (placed.length === 0) return grouped;
  const firstDay = placed[0].day;
  const ordered = [...news].sort((left, right) => Date.parse(left.time) - Date.parse(right.time));
  for (const item of ordered) {
    const instant = Date.parse(item.time);
    const day = easternParts(item.time).date;
    if (day < firstDay) continue;
    const before = lastBarAtOrBefore(placed, instant);
    const sameDay = before >= 0 && placed[before].day === day ? placed[before] : null;
    const target = sameDay ?? placed[before + 1];
    if (!target) continue;
    grouped.set(target.chartTime, [...(grouped.get(target.chartTime) ?? []), item]);
  }
  return grouped;
}
