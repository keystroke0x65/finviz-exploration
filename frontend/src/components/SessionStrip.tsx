import { useEffect, useState } from "react";
import {
  AFTER_HOURS_CLOSE,
  getMarketSession,
  PRE_MARKET_OPEN,
  REGULAR_CLOSE,
  REGULAR_OPEN,
  SessionPhase,
} from "../session";

const CLOCK_REFRESH_MS = 30_000;
const TRADING_DAY_MINUTES = AFTER_HOURS_CLOSE - PRE_MARKET_OPEN;

const SEGMENTS: { phase: Exclude<SessionPhase, "closed">; start: number; end: number }[] = [
  { phase: "pre-market", start: PRE_MARKET_OPEN, end: REGULAR_OPEN },
  { phase: "regular", start: REGULAR_OPEN, end: REGULAR_CLOSE },
  { phase: "after-hours", start: REGULAR_CLOSE, end: AFTER_HOURS_CLOSE },
];

const TIME_LABELS = [
  { text: "4 AM", minutes: PRE_MARKET_OPEN },
  { text: "9:30", minutes: REGULAR_OPEN },
  { text: "4 PM", minutes: REGULAR_CLOSE },
  { text: "8 PM", minutes: AFTER_HOURS_CLOSE },
];

const PHASE_NAMES: Record<SessionPhase, string> = {
  "pre-market": "Pre-market",
  regular: "Regular hours",
  "after-hours": "After-hours",
  closed: "Market closed",
};

function percentOfDay(minutes: number): number {
  return ((minutes - PRE_MARKET_OPEN) / TRADING_DAY_MINUTES) * 100;
}

export function SessionStrip() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), CLOCK_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, []);

  const session = getMarketSession(now);
  const easternTime = now.toLocaleTimeString("en-US", {
    timeZone: "America/New_York",
    hour: "numeric",
    minute: "2-digit",
  });

  return (
    <div className="session" aria-label="US market session, Eastern time">
      <div className="session-summary">
        <span className="session-phase" data-phase={session.phase}>
          {PHASE_NAMES[session.phase]}
        </span>
        <span>{easternTime} ET</span>
        <span className="session-next">{session.nextChange}</span>
      </div>
      <div className="session-track" aria-hidden="true">
        {SEGMENTS.map((segment) => (
          <div
            key={segment.phase}
            className="session-segment"
            data-segment={segment.phase}
            data-active={segment.phase === session.phase}
            style={{ width: `${((segment.end - segment.start) / TRADING_DAY_MINUTES) * 100}%` }}
            title={PHASE_NAMES[segment.phase]}
          />
        ))}
        {session.phase !== "closed" && (
          <div className="session-now" style={{ left: `${percentOfDay(session.minutesSinceMidnight)}%` }} />
        )}
      </div>
      <div className="session-labels" aria-hidden="true">
        {TIME_LABELS.map((label) => (
          <span key={label.text} style={{ left: `${percentOfDay(label.minutes)}%` }}>
            {label.text}
          </span>
        ))}
      </div>
    </div>
  );
}
