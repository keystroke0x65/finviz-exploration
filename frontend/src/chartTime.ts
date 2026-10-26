import { REGULAR_CLOSE, REGULAR_OPEN, SessionPhase } from "./session";

const EASTERN_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/**
 * lightweight-charts labels its time axis in UTC. Passing the Eastern
 * wall-clock time as if it were UTC makes the axis read in market time
 * (9:30 shows as 9:30) whatever the viewer's own timezone is.
 */
export function toChartTime(isoTime: string): number {
  const parts = Object.fromEntries(
    EASTERN_PARTS.formatToParts(new Date(isoTime)).map((part) => [part.type, Number(part.value)]),
  );
  return Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) / 1000;
}

export type BarSession = Exclude<SessionPhase, "closed">;

const SECONDS_PER_MINUTE = 60;
const MINUTES_PER_DAY = 24 * 60;

// Bars only exist from 4 AM to 8 PM, so anything before the open is pre-market
// and anything from the close on is after-hours.
export function barSession(isoTime: string): BarSession {
  const easternMinutes = Math.floor(toChartTime(isoTime) / SECONDS_PER_MINUTE) % MINUTES_PER_DAY;
  if (easternMinutes < REGULAR_OPEN) return "pre-market";
  if (easternMinutes < REGULAR_CLOSE) return "regular";
  return "after-hours";
}
