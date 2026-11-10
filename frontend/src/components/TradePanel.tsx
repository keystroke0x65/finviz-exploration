import { useEffect, useMemo, useState } from "react";
import type { Bar } from "../api/bars";
import {
  createEntry,
  DaySetup,
  fetchReasons,
  Fill,
  FillSide,
  JournalEntry,
  Preview,
  previewTrade,
  ReasonItem,
  TradeDraft,
  updateEntry,
} from "../api/journal";
import type { Direction } from "../api/setups";
import type { JournalSettings } from "../api/settings";
import { easternIso, easternParts, easternToday } from "../easternTime";
import { formatDollars, formatNumber, formatPrice, formatSignedDollars } from "../format";
import { suggestShares } from "../positionSize";
import { ReasonChips, toggled } from "./ReasonChips";
import { SetupPicker } from "./SetupPicker";

const PREVIEW_DELAY_MS = 300;
const FOLLOWED_PLAN = "followed_plan";

// A candle clicked on the chart; `id` changes on every click so the same candle can be clicked twice.
export interface ClickedBar {
  bar: Bar;
  id: number;
}

interface FillRow {
  key: number;
  side: FillSide;
  date: string;
  time: string;
  price: string;
  shares: string;
  // Range of the candle the row came from, to warn about a mistyped price.
  candle: { low: number; high: number } | null;
}

interface TradePanelProps {
  ticker: string;
  setups: DaySetup[];
  defaultSetupId: number | null;
  existing: JournalEntry | null;
  settings: JournalSettings | null;
  clickedBar: ClickedBar | null;
  onSaved: (entry: JournalEntry) => void;
  onClose: () => void;
}

let nextRowKey = 1;

function openingSide(direction: Direction): FillSide {
  return direction === "long" ? "buy" : "sell";
}

function closingSide(direction: Direction): FillSide {
  return direction === "long" ? "sell" : "buy";
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function parsePositive(text: string): number | null {
  const value = Number(text);
  return text.trim() !== "" && Number.isFinite(value) && value > 0 ? value : null;
}

function sharesHeld(rows: FillRow[], direction: Direction): number {
  return rows.reduce((held, row) => {
    const shares = parsePositive(row.shares) ?? 0;
    return row.side === openingSide(direction) ? held + shares : held - shares;
  }, 0);
}

function rowsFromEntry(entry: JournalEntry): FillRow[] {
  return entry.fills.map((fill) => ({
    key: nextRowKey++,
    side: fill.side,
    ...easternParts(fill.time),
    price: String(fill.price),
    shares: String(fill.shares),
    candle: null,
  }));
}

function isPriceOutsideCandle(row: FillRow): boolean {
  const price = parsePositive(row.price);
  return row.candle != null && price != null && (price < row.candle.low || price > row.candle.high);
}

function buildDraft(
  ticker: string,
  direction: Direction,
  setupId: number | null,
  plan: { stop: string; target: string },
  fees: string,
  mistakes: string[],
  note: string,
  rows: FillRow[],
): TradeDraft | null {
  const fills: Fill[] = [];
  for (const row of rows) {
    const price = parsePositive(row.price);
    const shares = parsePositive(row.shares);
    if (!row.date || !row.time || price == null || shares == null) return null;
    fills.push({ side: row.side, time: easternIso(row.date, row.time), price, shares: Math.round(shares) });
  }
  if (fills.length === 0) return null;
  return {
    kind: "trade",
    ticker,
    direction,
    setup_record_id: setupId,
    plan_stop: parsePositive(plan.stop),
    plan_target: parsePositive(plan.target),
    fees: Number(fees) || 0,
    mistakes,
    note,
    fills,
  };
}

function PreviewFigures({ preview }: { preview: Preview | null }) {
  if (!preview) return null;
  if (preview.error) return <p className="muted">{preview.error}</p>;
  const figures = preview.figures;
  if (!figures) return null;
  const pnlClass = figures.net_pnl > 0 ? "gain" : figures.net_pnl < 0 ? "loss" : "";
  return (
    <dl className="journal-preview">
      <div><dt className="plan-label">Avg entry</dt><dd>{formatPrice(figures.average_entry)}</dd></div>
      <div><dt className="plan-label">Avg exit</dt><dd>{formatPrice(figures.average_exit)}</dd></div>
      <div><dt className="plan-label">Held</dt><dd>{figures.shares_held}</dd></div>
      <div><dt className="plan-label">Money in</dt><dd>{formatDollars(figures.money_in)}</dd></div>
      <div><dt className="plan-label">P&amp;L</dt><dd className={pnlClass}>{formatSignedDollars(figures.net_pnl)}</dd></div>
      <div><dt className="plan-label">R</dt><dd className={pnlClass}>{figures.r_multiple == null ? "—" : `${formatNumber(figures.r_multiple)}R`}</dd></div>
      <div><dt className="plan-label">Status</dt><dd>{figures.status}</dd></div>
    </dl>
  );
}

function FillRowFields({
  row,
  index,
  onChange,
  onRemove,
}: {
  row: FillRow;
  index: number;
  onChange: (changed: FillRow) => void;
  onRemove: () => void;
}) {
  return (
    <fieldset className="fill-row" aria-label={`Fill ${index + 1}`}>
      <label>
        <span className="plan-label">Side</span>
        <select value={row.side} onChange={(event) => onChange({ ...row, side: event.target.value === "sell" ? "sell" : "buy" })}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </label>
      <label>
        <span className="plan-label">Date</span>
        <input type="date" value={row.date} onChange={(event) => onChange({ ...row, date: event.target.value })} />
      </label>
      <label>
        <span className="plan-label">Time (ET)</span>
        <input type="time" value={row.time} onChange={(event) => onChange({ ...row, time: event.target.value })} />
      </label>
      <label>
        <span className="plan-label">Price</span>
        <input type="number" min="0" step="0.0001" value={row.price}
          onChange={(event) => onChange({ ...row, price: event.target.value })} />
      </label>
      <label>
        <span className="plan-label">Shares</span>
        <input type="number" min="1" step="1" value={row.shares}
          onChange={(event) => onChange({ ...row, shares: event.target.value })} />
      </label>
      <button type="button" onClick={onRemove} aria-label={`Remove fill ${index + 1}`}>
        ×
      </button>
      {isPriceOutsideCandle(row) && row.candle && (
        <p className="fill-warning">
          Price is outside that candle's range ({formatPrice(row.candle.low)}–{formatPrice(row.candle.high)}).
        </p>
      )}
    </fieldset>
  );
}

export function TradePanel({
  ticker,
  setups,
  defaultSetupId,
  existing,
  settings,
  clickedBar,
  onSaved,
  onClose,
}: TradePanelProps) {
  const initialSetupId = existing ? existing.setup?.setup_record_id ?? null : defaultSetupId;
  const initialSetup = setups.find((setup) => setup.setup_record_id === initialSetupId) ?? null;
  const [direction, setDirection] = useState<Direction>(
    existing?.direction ?? (initialSetup?.direction === "short" ? "short" : "long"),
  );
  const [setupId, setSetupId] = useState<number | null>(initialSetupId);
  const [plan, setPlan] = useState({
    stop: String(existing ? existing.plan_stop ?? "" : initialSetup?.stop ?? ""),
    target: String(existing ? existing.plan_target ?? "" : initialSetup?.target ?? ""),
  });
  const [rows, setRows] = useState<FillRow[]>(() => (existing ? rowsFromEntry(existing) : []));
  const [mistakes, setMistakes] = useState<string[]>(existing?.mistakes ?? []);
  const [mistakeItems, setMistakeItems] = useState<ReasonItem[]>([]);
  const [fees, setFees] = useState(String(existing?.fees ?? 0));
  const [note, setNote] = useState(existing?.note ?? "");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReasons()
      .then((catalog) => setMistakeItems(catalog.mistakes))
      .catch((loadError: unknown) => setError(errorText(loadError)));
  }, []);

  useEffect(() => {
    if (!clickedBar) return;
    const { bar } = clickedBar;
    setRows((current) => {
      const held = sharesHeld(current, direction);
      const side = current.length === 0 ? openingSide(direction) : closingSide(direction);
      const shares = side === closingSide(direction) && held > 0 ? String(held) : "";
      return [
        ...current,
        { key: nextRowKey++, side, ...easternParts(bar.time), price: String(bar.close), shares,
          candle: { low: bar.low, high: bar.high } },
      ];
    });
    // Only a new click adds a row; direction changes must not replay the last click.
  }, [clickedBar?.id]);

  const draft = useMemo(
    () => buildDraft(ticker, direction, setupId, plan, fees, mistakes, note, rows),
    [ticker, direction, setupId, plan, fees, mistakes, note, rows],
  );
  const draftKey = draft ? JSON.stringify(draft) : null;

  useEffect(() => {
    if (!draft) {
      setPreview(null);
      return;
    }
    let isCurrent = true;
    const timer = setTimeout(() => {
      previewTrade(draft)
        .then((result) => {
          if (isCurrent) setPreview(result);
        })
        .catch((previewError: unknown) => {
          if (isCurrent) setPreview({ figures: null, error: errorText(previewError) });
        });
    }, PREVIEW_DELAY_MS);
    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
    // draftKey stands for draft: a new object with the same content must not re-preview.
  }, [draftKey]);

  function handleSetupChange(id: number | null) {
    setSetupId(id);
    const chosen = setups.find((setup) => setup.setup_record_id === id);
    if (!chosen) return;
    setDirection(chosen.direction === "short" ? "short" : "long");
    setPlan({ stop: String(chosen.stop), target: String(chosen.target) });
  }

  function addEmptyRow() {
    const side = rows.length === 0 ? openingSide(direction) : closingSide(direction);
    setRows([...rows, { key: nextRowKey++, side, date: easternToday(), time: "", price: "", shares: "", candle: null }]);
  }

  function toggleMistake(key: string) {
    if (key === FOLLOWED_PLAN) {
      setMistakes(mistakes.includes(FOLLOWED_PLAN) ? [] : [FOLLOWED_PLAN]);
      return;
    }
    setMistakes(toggled(mistakes.filter((existingKey) => existingKey !== FOLLOWED_PLAN), key));
  }

  async function handleSave() {
    if (!draft) return;
    setIsSaving(true);
    setError(null);
    try {
      onSaved(existing ? await updateEntry(existing.id, draft) : await createEntry(draft));
    } catch (saveError) {
      setError(errorText(saveError));
    } finally {
      setIsSaving(false);
    }
  }

  const sizingEntry = parsePositive(rows[0]?.price ?? "") ?? setups.find((setup) => setup.setup_record_id === setupId)?.entry;
  const sizingStop = parsePositive(plan.stop);
  const riskPerTrade = settings?.risk_per_trade ?? null;
  const suggested =
    riskPerTrade != null && sizingEntry != null && sizingStop != null
      ? suggestShares(riskPerTrade, sizingEntry, sizingStop, settings?.max_position ?? null)
      : null;

  return (
    <section className="journal-panel" aria-label={`Log trade in ${ticker}`}>
      <header className="journal-panel-header">
        <h3 className="editor-section-title">{existing ? `Trade in ${ticker}` : `Log trade in ${ticker}`}</h3>
        <button type="button" onClick={onClose} aria-label="Close">
          Close
        </button>
      </header>
      <p className="muted">Click a candle on the chart to add a fill at its time and close, or type one.</p>
      <div className="journal-row">
        <SetupPicker setups={setups} selectedId={setupId} onChange={handleSetupChange} />
        <label className="journal-field">
          <span className="plan-label">Direction</span>
          <select value={direction} onChange={(event) => setDirection(event.target.value === "short" ? "short" : "long")}>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </label>
        <label className="journal-field">
          <span className="plan-label">Plan stop</span>
          <input type="number" min="0" step="0.0001" value={plan.stop} aria-label="Plan stop"
            onChange={(event) => setPlan({ ...plan, stop: event.target.value })} />
        </label>
        <label className="journal-field">
          <span className="plan-label">Plan target</span>
          <input type="number" min="0" step="0.0001" value={plan.target} aria-label="Plan target"
            onChange={(event) => setPlan({ ...plan, target: event.target.value })} />
        </label>
      </div>
      {suggested != null && sizingEntry != null && riskPerTrade != null && (
        <p className="muted position-size">
          Size {suggested} sh ({formatDollars(suggested * sizingEntry)}) to risk {formatDollars(riskPerTrade)}
        </p>
      )}
      <div className="fill-rows">
        {rows.map((row, index) => (
          <FillRowFields
            key={row.key}
            row={row}
            index={index}
            onChange={(changed) => setRows(rows.map((existingRow) => (existingRow.key === row.key ? changed : existingRow)))}
            onRemove={() => setRows(rows.filter((existingRow) => existingRow.key !== row.key))}
          />
        ))}
      </div>
      <button type="button" onClick={addEmptyRow}>
        Add fill
      </button>
      <PreviewFigures preview={preview} />
      <div className="reason-group">
        <span className="plan-label">Mistakes</span>
        <ReasonChips items={mistakeItems} selected={mistakes} onToggle={toggleMistake} />
      </div>
      <div className="journal-row">
        <label className="journal-field">
          <span className="plan-label">Fees ($)</span>
          <input type="number" min="0" step="0.01" value={fees} onChange={(event) => setFees(event.target.value)} />
        </label>
        <label className="journal-field journal-note">
          <span className="plan-label">Note</span>
          <textarea value={note} maxLength={1000} rows={2} onChange={(event) => setNote(event.target.value)} />
        </label>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="journal-panel-actions">
        <button type="button" className="button-primary" disabled={!draft || isSaving} onClick={handleSave}>
          {isSaving ? "Saving…" : "Save trade"}
        </button>
      </div>
    </section>
  );
}
