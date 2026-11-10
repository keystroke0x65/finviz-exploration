import { useState } from "react";
import { JournalSettings, saveJournalSettings } from "../api/settings";

interface JournalSettingsPanelProps {
  settings: JournalSettings;
  onSaved: (settings: JournalSettings) => void;
}

type SettingName = keyof JournalSettings;

const FIELDS: [SettingName, string, string][] = [
  ["risk_per_trade", "Risk per trade ($)", "Sizes positions: shares = risk ÷ (entry − stop)."],
  ["max_position", "Max position ($)", "Caps the suggested size."],
  ["max_daily_loss", "Max daily loss ($)", "Amber note at 80%, red banner when reached. Never blocks."],
];

function toText(value: number | null): string {
  return value == null ? "" : String(value);
}

function toSetting(text: string): number | null {
  const value = Number(text);
  return text.trim() !== "" && Number.isFinite(value) && value > 0 ? value : null;
}

export function JournalSettingsPanel({ settings, onSaved }: JournalSettingsPanelProps) {
  const [texts, setTexts] = useState<Record<SettingName, string>>({
    risk_per_trade: toText(settings.risk_per_trade),
    max_position: toText(settings.max_position),
    max_daily_loss: toText(settings.max_daily_loss),
  });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    try {
      onSaved(
        await saveJournalSettings({
          risk_per_trade: toSetting(texts.risk_per_trade),
          max_position: toSetting(texts.max_position),
          max_daily_loss: toSetting(texts.max_daily_loss),
        }),
      );
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="journal-panel" aria-label="Risk settings">
      <div className="journal-row">
        {FIELDS.map(([name, label, hint]) => (
          <label key={name} className="journal-field" title={hint}>
            <span className="plan-label">{label}</span>
            <input type="number" min="0" step="1" aria-label={label} value={texts[name]}
              onChange={(event) => setTexts({ ...texts, [name]: event.target.value })} />
          </label>
        ))}
        <button type="button" className="button-primary" disabled={isSaving} onClick={handleSave}>
          {isSaving ? "Saving…" : "Save settings"}
        </button>
      </div>
      <p className="muted">Leave a box empty to turn that setting off.</p>
      {error && <p role="alert" className="alert">{error}</p>}
    </section>
  );
}
