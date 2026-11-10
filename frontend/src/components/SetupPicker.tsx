import type { DaySetup } from "../api/journal";
import { patternName } from "../api/setups";

interface SetupPickerProps {
  setups: DaySetup[];
  selectedId: number | null;
  onChange: (setupId: number | null) => void;
}

const NO_SETUP = "";

function describeSetup(setup: DaySetup): string {
  const grade = setup.sliding_scale ? ` · Sykes ${setup.sliding_scale.letter}` : "";
  return `${patternName(setup.pattern)} ${setup.timeframe} · ${setup.state} · score ${setup.score.toFixed(0)}${grade}`;
}

// Lists every setup the stock had that day (even ones already stopped out), as they looked at the trade time.
export function SetupPicker({ setups, selectedId, onChange }: SetupPickerProps) {
  return (
    <label className="journal-field">
      <span className="plan-label">Setup</span>
      <select
        value={selectedId == null ? NO_SETUP : String(selectedId)}
        onChange={(event) => onChange(event.target.value === NO_SETUP ? null : Number(event.target.value))}
      >
        <option value={NO_SETUP}>No setup</option>
        {setups.map((setup) => (
          <option key={setup.setup_record_id} value={String(setup.setup_record_id)}>
            {describeSetup(setup)}
          </option>
        ))}
      </select>
    </label>
  );
}
