import type { DaySetup, DaySetups, SetupSnapshot } from "../api/journal";
import { patternName } from "../api/setups";
import { formatPrice } from "../format";

interface SetupPickerProps {
  ticker: string;
  // null while loading.
  setups: DaySetups | null;
  selectedId: number | null;
  // Heading of the setups that fit the trade, e.g. "Best matches for your 9:45 AM buy at 0.76".
  matchLabel: string;
  // Label for the selected setup when the lists leave it out (a saved or earlier choice).
  selectedFallback: string | null;
  error: string | null;
  onChange: (setupId: number | null) => void;
}

const NO_SETUP = "";
const TRIGGER_TIME = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });

function describeGrade(setup: { sliding_scale: DaySetup["sliding_scale"] }): string {
  return setup.sliding_scale ? ` · Sykes ${setup.sliding_scale.letter}` : "";
}

// Entry price and trigger time are what tell two setups of the same pattern apart.
export function describeSetup(setup: DaySetup): string {
  const trigger = setup.triggered_at ? `triggered ${TRIGGER_TIME.format(new Date(setup.triggered_at))}` : setup.state;
  return `${patternName(setup.pattern)} ${setup.timeframe} · entry ${formatPrice(setup.entry)} · ${trigger} · score ${setup.score.toFixed(0)}${describeGrade(setup)}`;
}

// A saved entry's copy of its setup, for when the day's lists no longer offer that copy.
export function describeSavedSetup(setup: SetupSnapshot): string {
  return `${patternName(setup.pattern)} ${setup.timeframe} · entry ${formatPrice(setup.entry)} · saved setup · score ${setup.score.toFixed(0)}${describeGrade(setup)}`;
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

export function SetupPicker({ ticker, setups, selectedId, matchLabel, selectedFallback, error, onChange }: SetupPickerProps) {
  const listed = [...(setups?.matches ?? []), ...(setups?.others ?? [])];
  // Without its own option, a selected id would show as whichever option comes first.
  const isSelectedMissing = selectedId != null && setups != null && !listed.some((setup) => setup.setup_record_id === selectedId);
  return (
    <label className="journal-field">
      <span className="plan-label">Setup</span>
      <select
        value={selectedId == null ? NO_SETUP : String(selectedId)}
        onChange={(event) => onChange(event.target.value === NO_SETUP ? null : Number(event.target.value))}
      >
        {setups == null && <option disabled>Loading setups…</option>}
        {isSelectedMissing && selectedFallback && (
          <optgroup label="Chosen setup">
            <option value={String(selectedId)}>{selectedFallback}</option>
          </optgroup>
        )}
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
      {error && <span className="fill-warning">Couldn't load setups: {error}</span>}
    </label>
  );
}
