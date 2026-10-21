import type { Appearance } from "../api/watchlist";
import { formatEasternDate } from "../format";

const DAYS_SHOWN = 30;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

// Calendar days (YYYY-MM-DD, New York) from oldest to today.
function recentEasternDays(now: Date, count: number): string[] {
  const [year, month, day] = formatEasternDate(now.toISOString()).split("-").map(Number);
  const todayUtc = Date.UTC(year, month - 1, day);
  return Array.from({ length: count }, (_, index) =>
    new Date(todayUtc - (count - 1 - index) * MS_PER_DAY).toISOString().slice(0, 10),
  );
}

interface RunDotsProps {
  appearances: Appearance[];
}

export function RunDots({ appearances }: RunDotsProps) {
  const daysRan = new Set(appearances.map((appearance) => appearance.seen_on));
  const days = recentEasternDays(new Date(), DAYS_SHOWN);
  const ranCount = days.filter((day) => daysRan.has(day)).length;

  return (
    <span className="run-dots" role="img" aria-label={`Ran on ${ranCount} of the last ${DAYS_SHOWN} days`}>
      {days.map((day) => (
        <span key={day} className="run-dot" data-ran={daysRan.has(day)} title={day} />
      ))}
    </span>
  );
}
