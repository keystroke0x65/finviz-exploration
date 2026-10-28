import type { Bar } from "./api/bars";
import { formatPrice, formatSignedPercent } from "./format";

export interface BarLegendText {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
  change: string;
  volume: string;
  // Matches the candle colours: a bar that closed at its open counts as up.
  direction: "up" | "down";
}

const INTRADAY_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});
const DAILY_DATE = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  year: "numeric",
  month: "short",
  day: "numeric",
});

const VOLUME_UNITS: [number, string][] = [
  [1_000_000_000, "B"],
  [1_000_000, "M"],
  [1_000, "K"],
];

export function formatVolume(volume: number): string {
  for (const [size, suffix] of VOLUME_UNITS) {
    if (volume >= size) {
      return `${(volume / size).toFixed(1)}${suffix}`;
    }
  }
  return String(volume);
}

export function describeBar(bar: Bar, isDaily: boolean): BarLegendText {
  const changePercent = bar.open === 0 ? null : ((bar.close - bar.open) / bar.open) * 100;
  return {
    time: (isDaily ? DAILY_DATE : INTRADAY_TIME).format(new Date(bar.time)),
    open: formatPrice(bar.open),
    high: formatPrice(bar.high),
    low: formatPrice(bar.low),
    close: formatPrice(bar.close),
    change: formatSignedPercent(changePercent),
    volume: formatVolume(bar.volume),
    direction: bar.close >= bar.open ? "up" : "down",
  };
}
