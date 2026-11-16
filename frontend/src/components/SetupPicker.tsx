import type { DaySetup, DaySetups } from "../api/journal";
import { patternName } from "../api/setups";
import { formatPrice } from "../format";

interface SetupPickerProps {
  ticker: string;
  // null while loading.
  setups: DaySetups | null;
  selectedId: number | null;
  // Heading of the setups that fit the trade, e.g. "Best matches for your 9:45 AM buy at 0.76".
  matchLabel: string;
  onChange: (setupId: number | null) => void;
}

const NO_SETUP = "";
const TRIGGER_TIME = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });

// Entry price and trigger time are what tell two setups of the same pattern apart.
function describeSetup(setup: DaySetup): string {
  const trigger = setup.triggered_at ? `triggered ${TRIGGER_TIME.format(new Date(setup.triggered_at))}` : setup.state;
  const grade = setup.sliding_scale ? ` · Sykes ${setup.sliding_scale.letter}` : "";
  return `${patternName(setup.pattern)} ${setup.timeframe} · entry ${formatPrice(setup.entry)} · ${trigger} · score ${setup.score.toFixed(0)}${grade}`;
}

function SetupOptions({ setups }: { setups: DaySetup[] }) {
  return (
    <>
      {setups.map((setup) => (
        <option key={setup.setup_record_id} value={String(setup.setup_record_id)}>
          {describeSetup(setup)}
        </option>
      ))}
    </>
  );
}

export function SetupPicker({ ticker, setups, selectedId, matchLabel, onChange }: SetupPickerProps) {
  return (
    <label className="journal-field">
      <span className="plan-label">Setup</span>
      <select
        value={selectedId == null ? NO_SETUP : String(selectedId)}
        onChange={(event) => onChange(event.target.value === NO_SETUP ? null : Number(event.target.value))}
      >
        {setups == null && <option disabled>Loading setups…</option>}
        {setups && setups.matches.length > 0 && (
          <optgroup label={matchLabel}>
            <SetupOptions setups={setups.matches} />
          </optgroup>
        )}
        {setups && setups.others.length > 0 && (
          <optgroup label={`Other ${ticker} setups today (${setups.others.length})`}>
            <SetupOptions setups={setups.others} />
          </optgroup>
        )}
        <option value={NO_SETUP}>No setup</option>
      </select>
    </label>
  );
}
