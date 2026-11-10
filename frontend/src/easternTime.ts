// Fills are typed and shown in New York time, whatever the browser's own time zone.
const EASTERN_ZONE = "America/New_York";
const MINUTE_MS = 60_000;

const PARTS_FORMAT = new Intl.DateTimeFormat("en-CA", {
  timeZone: EASTERN_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export interface EasternParts {
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
}

export function easternParts(isoTime: string): EasternParts {
  const parts = Object.fromEntries(PARTS_FORMAT.formatToParts(new Date(isoTime)).map((part) => [part.type, part.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

function offsetMinutes(instant: Date): number {
  const { date, time } = easternParts(instant.toISOString());
  const asIfUtc = Date.parse(`${date}T${time}:00Z`);
  return Math.round((asIfUtc - Math.floor(instant.getTime() / MINUTE_MS) * MINUTE_MS) / MINUTE_MS);
}

function formatOffset(minutes: number): string {
  const sign = minutes < 0 ? "-" : "+";
  const absolute = Math.abs(minutes);
  const hours = String(Math.floor(absolute / 60)).padStart(2, "0");
  return `${sign}${hours}:${String(absolute % 60).padStart(2, "0")}`;
}

// "2026-11-09", "09:45" (Eastern) -> "2026-11-09T09:45:00-05:00".
export function easternIso(date: string, time: string): string {
  const guess = new Date(`${date}T${time}:00Z`);
  // The offset at the guessed instant is right for every trading hour (DST switches at 2 AM).
  const offset = offsetMinutes(new Date(guess.getTime() - offsetMinutes(guess) * MINUTE_MS));
  return `${date}T${time}:00${formatOffset(offset)}`;
}

export function easternToday(now: Date = new Date()): string {
  return easternParts(now.toISOString()).date;
}
