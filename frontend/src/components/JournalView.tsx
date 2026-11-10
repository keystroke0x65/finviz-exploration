import { useEffect, useMemo, useState } from "react";
import {
  Bucket,
  EntryKind,
  exportUrl,
  fetchEntries,
  fetchReasons,
  fetchSummary,
  JournalEntry,
  JournalPeriod,
  JournalSummary,
  ReasonCatalog,
} from "../api/journal";
import { patternName } from "../api/setups";
import { fetchJournalSettings, JournalSettings } from "../api/settings";
import { easternParts } from "../easternTime";
import {
  formatDollars,
  formatDuration,
  formatPrice,
  formatR,
  formatSignedDollars,
  formatSignedPercent,
  MISSING_VALUE,
} from "../format";
import { DailyLossBanner } from "./DailyLossBanner";
import { JournalEntryDetail } from "./JournalEntryDetail";
import { JournalSettingsPanel } from "./JournalSettingsPanel";
import { PnlChart } from "./PnlChart";
import { StockLink } from "./StockLink";

const PERIODS: [JournalPeriod, string][] = [
  ["today", "Today"],
  ["week", "This week"],
  ["month", "This month"],
  ["all", "All time"],
];
const KINDS: [EntryKind | null, string][] = [
  [null, "Both"],
  ["trade", "Trades"],
  ["pass", "Passes"],
];
const NO_SETUP = "no_setup";

interface JournalViewProps {
  onOpenStock: (ticker: string) => void;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function pnlClass(value: number | null): string {
  if (value == null || value === 0) return "";
  return value > 0 ? "gain" : "loss";
}

function formatRate(value: number | null): string {
  return value == null ? MISSING_VALUE : `${Math.round(value * 100)}%`;
}

function reasonLabels(catalog: ReasonCatalog | null): Record<string, string> {
  if (!catalog) return {};
  const items = [...catalog.pass_reasons.flatMap((group) => group.items), ...catalog.mistakes];
  return Object.fromEntries(items.map((item) => [item.key, item.label]));
}

function Tile({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="journal-tile">
      <span className="plan-label">{label}</span>
      <span className={`journal-tile-value ${className}`}>{value}</span>
    </div>
  );
}

function SummaryTiles({ summary }: { summary: JournalSummary }) {
  const sykes =
    summary.average_sykes_points == null
      ? MISSING_VALUE
      : `${summary.average_sykes_letter} · ${summary.average_sykes_points.toFixed(1)}/14`;
  return (
    <div className="journal-tiles">
      <Tile label="Net P&L" value={formatSignedDollars(summary.net_pnl)} className={pnlClass(summary.net_pnl)} />
      <Tile label="Trades" value={`${summary.trades}${summary.open_trades ? ` (+${summary.open_trades} open)` : ""}`} />
      <Tile label="Win rate" value={formatRate(summary.win_rate)} />
      <Tile label="Avg gain" value={formatDollars(summary.average_gain)} className="gain" />
      <Tile label="Avg loss" value={formatDollars(summary.average_loss)} className="loss" />
      <Tile label="Largest win" value={formatDollars(summary.largest_win)} />
      <Tile label="Largest loss" value={formatDollars(summary.largest_loss)} />
      <Tile label="Planned R:R" value={summary.average_planned_reward_risk == null ? MISSING_VALUE : `${summary.average_planned_reward_risk.toFixed(1)}R`} />
      <Tile label="Avg R made" value={formatR(summary.average_r)} className={pnlClass(summary.average_r)} />
      <Tile label="Avg duration" value={formatDuration(summary.average_duration_seconds)} />
      <Tile label="Avg Sykes grade" value={sykes} />
      <Tile label="Avg score" value={summary.average_score == null ? MISSING_VALUE : summary.average_score.toFixed(0)} />
      <Tile label="Left after exit" value={formatR(summary.average_left_on_table_r)} />
      <Tile label="Passes" value={String(summary.passes)} />
    </div>
  );
}

function BucketTable({ title, buckets, describe }: { title: string; buckets: Bucket[]; describe?: (label: string) => string }) {
  return (
    <table className="data-table journal-breakdown" aria-label={title}>
      <caption>{title}</caption>
      <thead>
        <tr><th></th><th>Trades</th><th>P&amp;L</th></tr>
      </thead>
      <tbody>
        {buckets.length === 0 && (
          <tr><td colSpan={3} className="muted">No closed trades</td></tr>
        )}
        {buckets.map((bucket) => (
          <tr key={bucket.label}>
            <td>{describe ? describe(bucket.label) : bucket.label}</td>
            <td>{bucket.count}</td>
            <td className={pnlClass(bucket.pnl)}>{bucket.count ? formatSignedDollars(bucket.pnl) : MISSING_VALUE}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PassReasonsTable({ summary, labels }: { summary: JournalSummary; labels: Record<string, string> }) {
  return (
    <table className="data-table journal-breakdown" aria-label="Passes by reason">
      <caption>Passes by reason (what the setup would have done)</caption>
      <thead>
        <tr>
          <th></th><th>Passes</th><th>Target</th><th>Stop</th><th>No fill</th><th>Undecided</th><th>Already past</th>
          <th>Avg R</th><th title="From the pass price, until 8 PM that day">Avg best after</th><th>Avg worst after</th>
        </tr>
      </thead>
      <tbody>
        {summary.pass_reasons.length === 0 && <tr><td colSpan={10} className="muted">No passes</td></tr>}
        {summary.pass_reasons.map((row) => (
          <tr key={row.reason}>
            <td>{labels[row.reason] ?? row.reason}</td>
            <td>{row.count}</td><td>{row.target}</td><td>{row.stop}</td><td>{row.never_filled}</td><td>{row.undecided}</td>
            <td>{row.already_past}</td>
            <td className={pnlClass(row.average_r)}>{formatR(row.average_r)}</td>
            <td className="gain">{formatSignedPercent(row.average_best_percent)}</td>
            <td className="loss">{formatSignedPercent(row.average_worst_percent)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function VersusTable({ summary }: { summary: JournalSummary }) {
  return (
    <table className="data-table journal-breakdown" aria-label="You vs. the system">
      <caption>You vs. the system (same pattern and timeframe)</caption>
      <thead>
        <tr><th>Pattern</th><th>Your trades</th><th>Your win rate</th><th>Your avg R</th><th>System trades</th><th>System win rate</th><th>System avg R</th></tr>
      </thead>
      <tbody>
        {summary.versus_system.length === 0 && <tr><td colSpan={7} className="muted">No trades with a setup</td></tr>}
        {summary.versus_system.map((row) => (
          <tr key={`${row.pattern}-${row.timeframe}`} className={row.system_has_enough_history ? "" : "muted"}
            title={row.system_has_enough_history ? undefined : "The system doesn't have enough history for this pattern yet"}>
            <td>{patternName(row.pattern)} {row.timeframe}</td>
            <td>{row.trades}</td>
            <td>{formatRate(row.win_rate)}</td>
            <td className={pnlClass(row.average_r)}>{formatR(row.average_r)}</td>
            <td>{row.system?.trades ?? MISSING_VALUE}</td>
            <td>{formatRate(row.system?.win_rate ?? null)}</td>
            <td>{formatR(row.system?.average_r ?? null)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function EntryRow({
  entry,
  labels,
  isSelected,
  onSelect,
  onOpenStock,
}: {
  entry: JournalEntry;
  labels: Record<string, string>;
  isSelected: boolean;
  onSelect: () => void;
  onOpenStock: (ticker: string) => void;
}) {
  const { date, time } = easternParts(entry.decided_at);
  const figures = entry.figures;
  const setup = entry.setup ? `${patternName(entry.setup.pattern)} ${entry.setup.timeframe}` : MISSING_VALUE;
  return (
    <tr aria-selected={isSelected}>
      <td>
        <button type="button" className="setup-select journal-open" onClick={onSelect} aria-label={`Open ${entry.ticker} ${entry.kind}`}>
          {date} {time}
        </button>
      </td>
      <td><StockLink ticker={entry.ticker} onOpen={onOpenStock} /></td>
      <td>{entry.kind === "trade" ? entry.direction : "pass"}</td>
      <td>{setup}</td>
      {figures ? (
        <>
          <td>{formatPrice(figures.average_entry)} → {formatPrice(figures.average_exit)}</td>
          <td>{figures.max_shares}</td>
          <td>{formatDollars(figures.money_in)}</td>
          <td className={pnlClass(figures.net_pnl)}>{formatSignedDollars(figures.net_pnl)}</td>
          <td className={pnlClass(figures.r_multiple)}>{formatR(figures.r_multiple)}</td>
          <td>{figures.status === "open" ? "open" : formatDuration(figures.duration_seconds)}</td>
        </>
      ) : (
        <td colSpan={6} className="muted">{entry.reasons.map((key) => labels[key] ?? key).join(", ")}</td>
      )}
    </tr>
  );
}

export function JournalView({ onOpenStock }: JournalViewProps) {
  const [period, setPeriod] = useState<JournalPeriod>("week");
  const [kind, setKind] = useState<EntryKind | null>(null);
  const [summary, setSummary] = useState<JournalSummary | null>(null);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [catalog, setCatalog] = useState<ReasonCatalog | null>(null);
  const [settings, setSettings] = useState<JournalSettings | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  // Bumped after an edit or delete so the summary and list reload.
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReasons().then(setCatalog).catch((loadError: unknown) => setError(errorText(loadError)));
    fetchJournalSettings().then(setSettings).catch((loadError: unknown) => setError(errorText(loadError)));
  }, []);

  useEffect(() => {
    let isCurrent = true;
    fetchSummary(period)
      .then((loaded) => {
        if (isCurrent) setSummary(loaded);
      })
      .catch((loadError: unknown) => {
        if (isCurrent) setError(errorText(loadError));
      });
    return () => {
      isCurrent = false;
    };
  }, [period, version]);

  useEffect(() => {
    let isCurrent = true;
    fetchEntries(kind, period)
      .then((loaded) => {
        if (isCurrent) setEntries(loaded);
      })
      .catch((loadError: unknown) => {
        if (isCurrent) setError(errorText(loadError));
      });
    return () => {
      isCurrent = false;
    };
  }, [kind, period, version]);

  const labels = useMemo(() => reasonLabels(catalog), [catalog]);
  const selected = entries.find((entry) => entry.id === selectedId) ?? null;

  function handleChanged(entry: JournalEntry) {
    setEntries(entries.map((existing) => (existing.id === entry.id ? entry : existing)));
    setVersion((current) => current + 1);
  }

  function handleDeleted(id: number) {
    setSelectedId(null);
    setEntries(entries.filter((entry) => entry.id !== id));
    setVersion((current) => current + 1);
  }

  return (
    <section className="journal-view">
      <DailyLossBanner refreshKey={version} />
      <div className="toolbar journal-toolbar">
        {PERIODS.map(([value, label]) => (
          <button key={value} type="button" className="tab" aria-pressed={period === value} onClick={() => setPeriod(value)}>
            {label}
          </button>
        ))}
        <span className="journal-buttons">
          <a href={exportUrl("entries", period)} download>Export entries (CSV)</a>
          <a href={exportUrl("fills", period)} download>Export fills (CSV)</a>
          <button type="button" aria-expanded={isSettingsOpen} onClick={() => setIsSettingsOpen(!isSettingsOpen)}>
            Risk settings
          </button>
        </span>
      </div>
      {isSettingsOpen && settings && (
        <JournalSettingsPanel
          settings={settings}
          onSaved={(saved) => {
            setSettings(saved);
            setIsSettingsOpen(false);
            setVersion((current) => current + 1);
          }}
        />
      )}
      {error && <p role="alert" className="alert">{error}</p>}
      {summary && (
        <>
          <SummaryTiles summary={summary} />
          {summary.pnl_points.length > 0 ? (
            <PnlChart points={summary.pnl_points} />
          ) : (
            <p className="muted">No realised P&amp;L in this period yet.</p>
          )}
        </>
      )}

      <div className="toolbar journal-toolbar">
        {KINDS.map(([value, label]) => (
          <button key={label} type="button" className="tab" aria-pressed={kind === value} onClick={() => setKind(value)}>
            {label}
          </button>
        ))}
      </div>
      <div className="journal-layout">
        <div className="table-scroll">
          <table className="data-table journal-entries" aria-label="Journal entries">
            <thead>
              <tr>
                <th>When (ET)</th><th>Ticker</th><th>Type</th><th>Setup</th><th>Entry → exit</th><th>Shares</th>
                <th>Money in</th><th>P&amp;L</th><th>R</th><th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 && (
                <tr><td colSpan={10} className="muted">Nothing logged in this period. Log trades and passes from the Stock tab.</td></tr>
              )}
              {entries.map((entry) => (
                <EntryRow key={entry.id} entry={entry} labels={labels} isSelected={entry.id === selectedId}
                  onSelect={() => setSelectedId(entry.id)} onOpenStock={onOpenStock} />
              ))}
            </tbody>
          </table>
        </div>
        {selected && (
          <JournalEntryDetail entry={selected} labels={labels} settings={settings} onChanged={handleChanged}
            onDeleted={handleDeleted} />
        )}
      </div>

      {summary && (
        <div className="journal-breakdowns">
          <BucketTable title="By pattern" buckets={summary.by_pattern}
            describe={(label) => (label === NO_SETUP ? "No setup" : patternName(label))} />
          <BucketTable title="By mistake" buckets={summary.by_mistake} describe={(label) => labels[label] ?? label} />
          <BucketTable title="By time of day" buckets={summary.by_time_of_day} />
          <BucketTable title="By duration" buckets={summary.by_duration} />
          <BucketTable title="By country" buckets={summary.by_country} />
          <BucketTable title="By industry" buckets={summary.by_industry} />
          <PassReasonsTable summary={summary} labels={labels} />
          <VersusTable summary={summary} />
        </div>
      )}
    </section>
  );
}
