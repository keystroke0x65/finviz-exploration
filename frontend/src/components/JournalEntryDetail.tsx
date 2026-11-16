import { useEffect, useRef, useState } from "react";
import type { Bar } from "../api/bars";
import {
  AfterPass,
  deleteEntry,
  EntryBars,
  fetchEntryBars,
  JournalEntry,
  PassOutcome,
  PlanFlag,
} from "../api/journal";
import { patternName } from "../api/setups";
import type { JournalSettings } from "../api/settings";
import { easternParts } from "../easternTime";
import { formatDollars, formatDuration, formatPrice, formatR, formatSignedDollars, formatSignedPercent } from "../format";
import { CandleChart, ChartLevel } from "./CandleChart";
import { PassPanel } from "./PassPanel";
import { ClickedBar, TradePanel } from "./TradePanel";

type Interval = "1m" | "5m";

const PLAN_FLAG_LABELS: Record<PlanFlag, string> = {
  exited_before_target: "Exited before target",
  held_past_stop: "Held past stop",
  followed_plan: "Followed the plan",
};

interface JournalEntryDetailProps {
  entry: JournalEntry;
  // Labels of pass reasons and mistakes by key.
  labels: Record<string, string>;
  settings: JournalSettings | null;
  onChanged: (entry: JournalEntry) => void;
  onDeleted: (id: number) => void;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function describeDay(day: string): string {
  return new Date(`${day}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function dayNotice({ day, status }: EntryBars["days"][number]): string | null {
  if (status === "missing") return `Bars for ${describeDay(day)} are no longer available from Finviz.`;
  if (status === "incomplete") return `Bars for ${describeDay(day)} are only partly saved; Finviz no longer has the rest.`;
  if (status === "partial") return `Bars for ${describeDay(day)} are saved up to now; the rest is saved after 8 PM ET.`;
  if (status == null) return `Bars for ${describeDay(day)} aren't saved yet; the app retries every 15 minutes.`;
  return null;
}

function describePassOutcome(outcome: PassOutcome, r: number | null): string {
  if (outcome === "target") return `Would have hit the target (${formatR(r)})`;
  if (outcome === "stop") return `Would have stopped out (${formatR(r)})`;
  if (outcome === "never_filled") return "Would never have reached its entry";
  if (outcome === "undecided") return "Hadn't hit its stop or target by 8 PM";
  if (outcome === "past_target") return "Already past the target when you passed";
  if (outcome === "behind_stop") return "Already behind the stop when you passed";
  return "No setup linked, so no stop or target to score against";
}

function afterExitLines(entry: JournalEntry): string[] {
  const after = entry.after_exit;
  if (!after) return [];
  if (after.best_r == null || after.worst_r == null) {
    if (after.best_price == null) return ["No bars after your exit that day."];
    return [`After you sold: best ${formatPrice(after.best_price)}, worst ${formatPrice(after.worst_price)}`];
  }
  const lines: string[] = [];
  if (after.best_r > 0) lines.push(`Kept going ${formatR(after.best_r)} after you sold`);
  if (after.worst_r < 0) lines.push(`Dropped ${Math.abs(after.worst_r).toFixed(2)}R after you sold`);
  return lines;
}

function afterPassLine(after: AfterPass): string {
  const withR = (percent: number, r: number | null) =>
    r == null ? formatSignedPercent(percent) : `${formatSignedPercent(percent)}, ${formatR(r)}`;
  return (
    `After you passed: high ${formatPrice(after.best_price)} (${withR(after.best_percent, after.best_r)}), ` +
    `low ${formatPrice(after.worst_price)} (${withR(after.worst_percent, after.worst_r)})`
  );
}

function chartLevels(entry: JournalEntry): ChartLevel[] {
  const levels: ChartLevel[] = [];
  if (entry.plan_stop != null) levels.push({ price: entry.plan_stop, label: "Plan stop", kind: "stop" });
  if (entry.plan_target != null) levels.push({ price: entry.plan_target, label: "Plan target", kind: "target" });
  if (entry.kind === "pass" && entry.setup) levels.push({ price: entry.setup.entry, label: "Entry", kind: "entry" });
  return levels;
}

function TradeFacts({ entry, labels }: { entry: JournalEntry; labels: Record<string, string> }) {
  const figures = entry.figures;
  if (!figures) return null;
  const pnlClass = figures.net_pnl > 0 ? "gain" : figures.net_pnl < 0 ? "loss" : "";
  return (
    <>
      <dl className="journal-preview">
        <div><dt className="plan-label">P&amp;L</dt><dd className={pnlClass}>{formatSignedDollars(figures.net_pnl)}</dd></div>
        <div><dt className="plan-label">R</dt><dd className={pnlClass}>{formatR(figures.r_multiple)}</dd></div>
        <div><dt className="plan-label">Avg entry</dt><dd>{formatPrice(figures.average_entry)}</dd></div>
        <div><dt className="plan-label">Avg exit</dt><dd>{formatPrice(figures.average_exit)}</dd></div>
        <div><dt className="plan-label">Shares</dt><dd>{figures.max_shares}</dd></div>
        <div><dt className="plan-label">Money in</dt><dd>{formatDollars(figures.money_in)}</dd></div>
        <div><dt className="plan-label">Planned R:R</dt><dd>{figures.planned_reward_risk == null ? "—" : `${figures.planned_reward_risk.toFixed(1)}R`}</dd></div>
        <div><dt className="plan-label">Duration</dt><dd>{formatDuration(figures.duration_seconds)}</dd></div>
        <div><dt className="plan-label">Status</dt><dd>{figures.shares_held > 0 ? `open, ${figures.shares_held} held` : "closed"}</dd></div>
      </dl>
      <ul className="journal-flags">
        {entry.plan_flags.map((flag) => <li key={flag}>{PLAN_FLAG_LABELS[flag]}</li>)}
        {afterExitLines(entry).map((line) => <li key={line}>{line}</li>)}
      </ul>
      {entry.mistakes.length > 0 && (
        <p className="reason-chips">
          {entry.mistakes.map((key) => <span key={key} className="reason-chip">{labels[key] ?? key}</span>)}
        </p>
      )}
    </>
  );
}

function PassFacts({ entry, labels }: { entry: JournalEntry; labels: Record<string, string> }) {
  return (
    <>
      <p className="reason-chips">
        {entry.reasons.map((key) => <span key={key} className="reason-chip">{labels[key] ?? key}</span>)}
      </p>
      <ul className="journal-flags">
        <li>Passed at {formatPrice(entry.pass_price)}</li>
        {entry.pass_score && <li>{describePassOutcome(entry.pass_score.outcome, entry.pass_score.r)}</li>}
        {entry.after_pass && <li>{afterPassLine(entry.after_pass)}</li>}
      </ul>
    </>
  );
}

function SetupFacts({ entry }: { entry: JournalEntry }) {
  const { setup, stock } = entry;
  return (
    <p className="muted">
      {setup
        ? `${patternName(setup.pattern)} ${setup.timeframe} · ${setup.state} · score ${setup.score.toFixed(0)}` +
          (setup.sliding_scale ? ` · Sykes ${setup.sliding_scale.letter} (${setup.sliding_scale.points}/14)` : "")
        : "No setup linked"}
      {" · "}
      {[stock.country, stock.industry].filter(Boolean).join(", ") || "No stock facts"}
    </p>
  );
}

function FillsTable({ entry }: { entry: JournalEntry }) {
  if (entry.fills.length === 0) return null;
  return (
    <table className="data-table fills-table">
      <thead>
        <tr><th>Side</th><th>Date</th><th>Time (ET)</th><th>Price</th><th>Shares</th></tr>
      </thead>
      <tbody>
        {entry.fills.map((fill) => {
          const { date, time } = easternParts(fill.time);
          return (
            <tr key={`${fill.time}-${fill.side}-${fill.price}`}>
              <td>{fill.side}</td><td>{date}</td><td>{time}</td><td>{formatPrice(fill.price)}</td><td>{fill.shares}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function JournalEntryDetail({ entry, labels, settings, onChanged, onDeleted }: JournalEntryDetailProps) {
  const [chartInterval, setChartInterval] = useState<Interval>("1m");
  const [bars, setBars] = useState<EntryBars | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [clickedBar, setClickedBar] = useState<ClickedBar | null>(null);
  const clickCount = useRef(0);
  const screenshotRef = useRef<(() => HTMLCanvasElement) | null>(null);

  useEffect(() => {
    let isCurrent = true;
    setBars(null);
    fetchEntryBars(entry.id, chartInterval)
      .then((loaded) => {
        if (isCurrent) setBars(loaded);
      })
      .catch((loadError: unknown) => {
        if (isCurrent) setError(errorText(loadError));
      });
    return () => {
      isCurrent = false;
    };
  }, [entry.id, entry.updated_at, chartInterval]);

  useEffect(() => setIsEditing(false), [entry.id]);

  function handleEdit() {
    setIsEditing(true);
  }

  async function handleDelete() {
    if (!window.confirm(`Delete this ${entry.kind} in ${entry.ticker}? This can't be undone.`)) return;
    try {
      await deleteEntry(entry.id);
      onDeleted(entry.id);
    } catch (deleteError) {
      setError(errorText(deleteError));
    }
  }

  function handleSaveImage() {
    const canvas = screenshotRef.current?.();
    if (!canvas) return;
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${entry.ticker}-${easternParts(entry.decided_at).date}-${entry.kind}.png`;
    link.click();
  }

  function handleBarClick(bar: Bar) {
    if (!isEditing || entry.kind !== "trade") return;
    clickCount.current += 1;
    setClickedBar({ bar, id: clickCount.current });
  }

  function handleSaved(saved: JournalEntry) {
    setIsEditing(false);
    onChanged(saved);
  }

  const notices = (bars?.days ?? []).map(dayNotice).filter((notice): notice is string => notice != null);

  return (
    <article className="journal-detail" aria-label={`${entry.kind} in ${entry.ticker}`}>
      <header className="journal-panel-header">
        <h3 className="editor-section-title">
          {entry.ticker} · {entry.kind === "trade" ? `${entry.direction} trade` : "pass"} ·{" "}
          {easternParts(entry.decided_at).date} {easternParts(entry.decided_at).time} ET
        </h3>
        <span className="journal-buttons">
          <button type="button" onClick={handleEdit}>Edit</button>
          <button type="button" onClick={handleSaveImage}>Save as image</button>
          <button type="button" onClick={handleDelete}>Delete</button>
        </span>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      <SetupFacts entry={entry} />
      {entry.kind === "trade" ? <TradeFacts entry={entry} labels={labels} /> : <PassFacts entry={entry} labels={labels} />}
      {entry.note && <p className="journal-note-text">{entry.note}</p>}
      <div className="toolbar chart-toolbar">
        {(["1m", "5m"] as const).map((option) => (
          <button key={option} type="button" className="tab" aria-pressed={chartInterval === option} onClick={() => setChartInterval(option)}>
            {option}
          </button>
        ))}
      </div>
      {notices.map((notice) => <p key={notice} className="muted">{notice}</p>)}
      {bars && bars.bars.length > 0 && (
        <CandleChart
          bars={bars.bars}
          levels={chartLevels(entry)}
          outline={null}
          vwap={null}
          shadeSessions
          markers={entry.fills}
          onBarClick={handleBarClick}
          screenshotRef={screenshotRef}
        />
      )}
      <FillsTable entry={entry} />
      {isEditing && entry.kind === "trade" && (
        <TradePanel
          ticker={entry.ticker}
          preferredSetupId={entry.setup?.setup_record_id ?? null}
          preferredDirection={entry.direction}
          existing={entry}
          settings={settings}
          clickedBar={clickedBar}
          onSaved={handleSaved}
          onClose={() => setIsEditing(false)}
        />
      )}
      {isEditing && entry.kind === "pass" && (
        <PassPanel
          ticker={entry.ticker}
          preferredSetupId={entry.setup?.setup_record_id ?? null}
          existing={entry}
          onSaved={handleSaved}
          onClose={() => setIsEditing(false)}
        />
      )}
    </article>
  );
}
