// US equity sessions in New York time. Exchange holidays aren't modelled:
// on a holiday the strip shows a session that isn't actually trading.
export type SessionPhase = "pre-market" | "regular" | "after-hours" | "closed";

export interface MarketSession {
  phase: SessionPhase;
  minutesSinceMidnight: number;
  nextChange: string;
}

export const PRE_MARKET_OPEN = 4 * 60;
export const REGULAR_OPEN = 9 * 60 + 30;
export const REGULAR_CLOSE = 16 * 60;
export const AFTER_HOURS_CLOSE = 20 * 60;

const EASTERN_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function easternClock(now: Date): { weekday: string; minutesSinceMidnight: number } {
  const parts = Object.fromEntries(EASTERN_PARTS.formatToParts(now).map((part) => [part.type, part.value]));
  return { weekday: parts.weekday, minutesSinceMidnight: Number(parts.hour) * 60 + Number(parts.minute) };
}

function closedMessage(weekday: string, minutesSinceMidnight: number): string {
  const isBeforeOpenOnWeekday = minutesSinceMidnight < PRE_MARKET_OPEN && weekday !== "Sat" && weekday !== "Sun";
  const isWeekendNext = weekday === "Sat" || weekday === "Sun" || (weekday === "Fri" && !isBeforeOpenOnWeekday);
  return isWeekendNext ? "Pre-market opens Monday at 4:00 AM ET" : "Pre-market opens at 4:00 AM ET";
}

export function getMarketSession(now: Date): MarketSession {
  const { weekday, minutesSinceMidnight } = easternClock(now);
  const isWeekend = weekday === "Sat" || weekday === "Sun";

  if (isWeekend || minutesSinceMidnight < PRE_MARKET_OPEN || minutesSinceMidnight >= AFTER_HOURS_CLOSE) {
    return { phase: "closed", minutesSinceMidnight, nextChange: closedMessage(weekday, minutesSinceMidnight) };
  }
  if (minutesSinceMidnight < REGULAR_OPEN) {
    return { phase: "pre-market", minutesSinceMidnight, nextChange: "Regular hours open at 9:30 AM ET" };
  }
  if (minutesSinceMidnight < REGULAR_CLOSE) {
    return { phase: "regular", minutesSinceMidnight, nextChange: "Regular hours close at 4:00 PM ET" };
  }
  return { phase: "after-hours", minutesSinceMidnight, nextChange: "After-hours ends at 8:00 PM ET" };
}
