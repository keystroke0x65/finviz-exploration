import { useEffect, useRef, useState } from "react";
import { createEntry, fetchReasons, JournalEntry, PassDraft, ReasonCatalog, updateEntry } from "../api/journal";
import { ReasonChips, toggled } from "./ReasonChips";
import { describeSavedSetup, SetupPicker } from "./SetupPicker";
import { useDaySetups } from "../useDaySetups";

const OTHER_REASON = "other";

interface PassPanelProps {
  ticker: string;
  // The setup picked on the Stock page, chosen first if it's live now.
  preferredSetupId: number | null;
  // A saved pass being edited; it keeps the moment it was made.
  existing?: JournalEntry | null;
  onSaved: (entry: JournalEntry) => void;
  onClose: () => void;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function PassPanel({ ticker, preferredSetupId, existing = null, onSaved, onClose }: PassPanelProps) {
  const [catalog, setCatalog] = useState<ReasonCatalog | null>(null);
  const [reasons, setReasons] = useState<string[]>(existing?.reasons ?? []);
  const [note, setNote] = useState(existing?.note ?? "");
  const [setupId, setSetupId] = useState<number | null>(existing ? existing.setup?.setup_record_id ?? null : null);
  // Once the user (or a saved pass) has a setup, new matches must not swap it.
  const isSetupChosen = useRef(existing != null);
  // A pass is matched at its own moment (now, or when a saved pass was made), in any direction.
  const { setups: daySetups, error: setupsError } = useDaySetups(
    ticker, existing ? { time: existing.decided_at, price: existing.pass_price } : null, null,
  );
  const allSetups = [...(daySetups?.matches ?? []), ...(daySetups?.others ?? [])];

  useEffect(() => {
    if (!daySetups || isSetupChosen.current) return;
    const best =
      daySetups.matches.find((setup) => setup.setup_record_id === preferredSetupId) ?? daySetups.matches[0] ?? null;
    setSetupId(best?.setup_record_id ?? null);
  }, [daySetups, preferredSetupId]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReasons()
      .then(setCatalog)
      .catch((loadError: unknown) => setError(errorText(loadError)));
  }, []);

  const needsNote = reasons.includes(OTHER_REASON) && !note.trim();
  const canSave = reasons.length > 0 && !needsNote && !isSaving;
  const direction = allSetups.find((setup) => setup.setup_record_id === setupId)?.direction === "short" ? "short" : "long";

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    try {
      const draft: PassDraft = {
        kind: "pass", ticker, direction, setup_record_id: setupId, reasons, note, decided_at: existing?.decided_at ?? null,
      };
      onSaved(existing ? await updateEntry(existing.id, draft) : await createEntry(draft));
    } catch (saveError) {
      setError(errorText(saveError));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="journal-panel" aria-label={`Pass on ${ticker}`}>
      <header className="journal-panel-header">
        <h3 className="editor-section-title">Pass on {ticker}</h3>
        <button type="button" onClick={onClose} aria-label="Close">
          Close
        </button>
      </header>
      <SetupPicker
        ticker={ticker}
        setups={daySetups}
        selectedId={setupId}
        matchLabel={existing ? "Setups live when you passed" : "Setups live now"}
        selectedFallback={
          existing?.setup && existing.setup.setup_record_id === setupId ? describeSavedSetup(existing.setup) : null
        }
        error={setupsError}
        onChange={(id) => {
          isSetupChosen.current = true;
          setSetupId(id);
        }}
      />
      {catalog?.pass_reasons.map((group) => (
        <div key={group.group} className="reason-group">
          <span className="plan-label">{group.group}</span>
          <ReasonChips items={group.items} selected={reasons} onToggle={(key) => setReasons(toggled(reasons, key))} />
        </div>
      ))}
      <label className="journal-field">
        <span className="plan-label">Note</span>
        <textarea value={note} maxLength={1000} rows={2} onChange={(event) => setNote(event.target.value)} />
      </label>
      {needsNote && <p className="muted">Add a note to explain "Other".</p>}
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="journal-panel-actions">
        <button type="button" className="button-primary" disabled={!canSave} onClick={handleSave}>
          {isSaving ? "Saving…" : "Save pass"}
        </button>
      </div>
    </section>
  );
}
