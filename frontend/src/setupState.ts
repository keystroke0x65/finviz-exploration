import type { Setup } from "./api/setups";

type SetupStateFields = Pick<Setup, "state" | "triggered_at" | "timeframe">;

const STATE_NAMES: Record<Setup["state"], string> = {
  forming: "Forming",
  triggered: "Triggered",
  extended: "Extended",
  invalidated: "Invalidated",
};

const EASTERN_CLOCK = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "numeric",
  minute: "2-digit",
});
const EASTERN_DAY = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric" });

function formatTriggerMoment(triggeredAt: string, timeframe: Setup["timeframe"]): string {
  const moment = new Date(triggeredAt);
  return timeframe === "daily" ? EASTERN_DAY.format(moment) : EASTERN_CLOCK.format(moment);
}

// "Triggered 9:42 AM": the time comes from the bar that reached the entry, which can be
// several minutes before the scan that noticed it.
export function describeSetupState({ state, triggered_at, timeframe }: SetupStateFields): string {
  if (!triggered_at || (state !== "triggered" && state !== "extended")) return STATE_NAMES[state];
  const moment = formatTriggerMoment(triggered_at, timeframe);
  return state === "triggered" ? `Triggered ${moment}` : `Extended, triggered ${moment}`;
}
