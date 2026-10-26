import type { ScanStatus } from "./api/setups";

export interface ScanStatusNote {
  isProblem: boolean;
  text: string;
}

const EASTERN_CLOCK = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });
const EASTERN_DAY_AND_CLOCK = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});
const EASTERN_DATE = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" });

function formatScanTime(isoTimestamp: string, now: Date): string {
  const moment = new Date(isoTimestamp);
  const isToday = EASTERN_DATE.format(moment) === EASTERN_DATE.format(now);
  return (isToday ? EASTERN_CLOCK : EASTERN_DAY_AND_CLOCK).format(moment);
}

// A crash or a stall means the setups on screen are older than they look, so those
// read as problems; a clean or partly failed scan is just noted.
export function describeScanStatus(status: ScanStatus, now: Date): ScanStatusNote {
  const { latest, last_completed_at: lastCompletedAt } = status;
  if (latest?.status === "crashed") {
    const failedAt = formatScanTime(latest.finished_at, now);
    const age = lastCompletedAt
      ? `, so these setups are from the ${formatScanTime(lastCompletedAt, now)} scan`
      : " and no scan has completed yet";
    return { isProblem: true, text: `The ${failedAt} scan failed (${latest.error_type})${age}. Details are in the backend log.` };
  }
  if (status.is_overdue) {
    const since = lastCompletedAt ? `since ${formatScanTime(lastCompletedAt, now)}` : "today";
    return {
      isProblem: true,
      text: `No scan has finished ${since}; they should run every 15 minutes from 4 AM to 8 PM ET. These setups may be out of date.`,
    };
  }
  if (!latest) return { isProblem: false, text: "No full scan yet" };
  const unreachable = latest.failed.length > 0 ? `, ${latest.failed.length} couldn't be scanned` : "";
  return {
    isProblem: false,
    text: `Last scan ${formatScanTime(latest.finished_at, now)} · ${latest.scanned} stocks${unreachable}`,
  };
}
