import { useRef, useState } from "react";
import type { ColumnWidths } from "../api/settings";
import type { ScreenRow, ScreenRun, ScreenSetup } from "../api/screens";
import { patternName } from "../api/setups";
import {
  changeClass,
  finvizQuoteUrl,
  formatCount,
  formatNewsTime,
  formatNumber,
  formatSignedPercent,
  isWebUrl,
  MISSING_VALUE,
} from "../format";
import { clampColumnWidth, MAX_COLUMN_WIDTH, MIN_COLUMN_WIDTH, useScreenColumnWidths } from "../screenColumnWidths";
import { SlidingScaleBadge } from "./SlidingScaleBadge";
import { StockLink } from "./StockLink";
import { VerdictBadge } from "./VerdictBadge";

interface ScreenResultsTableProps {
  run: ScreenRun;
  onAddToWatchlist: (ticker: string) => void;
  watchlistTickers: Set<string>;
  onOpenStock: (ticker: string) => void;
}

type SortableColumn = keyof Pick<
  ScreenRow,
  | "ticker"
  | "price"
  | "change_percent"
  | "after_hours_change_percent"
  | "volume"
  | "relative_volume"
  | "float_millions"
  | "market_cap_millions"
>;

interface Column {
  key: SortableColumn;
  label: string;
  isNumeric: boolean;
}

const COLUMNS: Column[] = [
  { key: "ticker", label: "Ticker", isNumeric: false },
  { key: "price", label: "Price", isNumeric: true },
  { key: "change_percent", label: "Change", isNumeric: true },
  { key: "after_hours_change_percent", label: "After-hours", isNumeric: true },
  { key: "volume", label: "Volume", isNumeric: true },
  { key: "relative_volume", label: "Rel vol", isNumeric: true },
  { key: "float_millions", label: "Float (M)", isNumeric: true },
  { key: "market_cap_millions", label: "Mkt cap (M)", isNumeric: true },
];

// The headers after the sortable ones; actions has no label or resize handle.
const OTHER_HEADERS: { key: string; label: string; isNumeric: boolean }[] = [
  { key: "news", label: "Latest news", isNumeric: false },
  { key: "score", label: "Score", isNumeric: true },
  { key: "sykes", label: "Sykes", isNumeric: true },
  { key: "verdict", label: "Verdict", isNumeric: false },
];
const ACTIONS_KEY = "actions";
const WIDTH_KEYS = [...COLUMNS.map((column) => column.key), ...OTHER_HEADERS.map((header) => header.key), ACTIONS_KEY];
// For a column added after a layout was saved.
const DEFAULT_COLUMN_WIDTH = 100;
const KEYBOARD_STEPS: Record<string, number> = { ArrowLeft: -10, ArrowRight: 10 };

interface SortState {
  column: SortableColumn;
  isDescending: boolean;
}

function compareRows(left: ScreenRow, right: ScreenRow, sort: SortState): number {
  const leftValue = left[sort.column];
  const rightValue = right[sort.column];
  // Missing values always sink to the bottom, whichever direction is chosen.
  if (leftValue == null) return rightValue == null ? 0 : 1;
  if (rightValue == null) return -1;
  const order = leftValue < rightValue ? -1 : leftValue > rightValue ? 1 : 0;
  return sort.isDescending ? -order : order;
}

function TopSetupCells({ setup, ticker }: { setup: ScreenSetup | null | undefined; ticker: string }) {
  if (!setup) {
    return (
      <>
        <td className="number">{MISSING_VALUE}</td>
        <td className="number">{MISSING_VALUE}</td>
      </>
    );
  }
  return (
    <>
      <td className="number">
        {setup.score.toFixed(0)}
        {/* A stock can have several setups; say which one the score belongs to. */}
        <div className="muted top-setup-name">
          {patternName(setup.pattern)} {setup.timeframe}
        </div>
      </td>
      <td className="number">
        {setup.sliding_scale ? <SlidingScaleBadge scale={setup.sliding_scale} ticker={ticker} /> : MISSING_VALUE}
      </td>
    </>
  );
}

interface ColumnResizerProps {
  label: string;
  width: number | undefined;
  onDragStart: (startX: number) => void;
  onStep: (step: number) => void;
}

function ColumnResizer({ label, width, onDragStart, onStep }: ColumnResizerProps) {
  return (
    <span
      role="separator"
      aria-orientation="vertical"
      aria-label={`Resize ${label} column`}
      aria-valuenow={width}
      aria-valuemin={MIN_COLUMN_WIDTH}
      aria-valuemax={MAX_COLUMN_WIDTH}
      tabIndex={0}
      className="column-resizer"
      onMouseDown={(event) => {
        event.preventDefault(); // don't start selecting header text
        onDragStart(event.clientX);
      }}
      onKeyDown={(event) => {
        const step = KEYBOARD_STEPS[event.key];
        if (step === undefined) return;
        event.preventDefault();
        onStep(step);
      }}
    />
  );
}

export function ScreenResultsTable({ run, onAddToWatchlist, watchlistTickers, onOpenStock }: ScreenResultsTableProps) {
  // Null keeps Finviz's own order (the screen's sort setting).
  const [sort, setSort] = useState<SortState | null>(null);
  const columnWidths = useScreenColumnWidths();
  const headerCells = useRef<Record<string, HTMLTableCellElement | null>>({});

  // The first resize pins every column at the width it has now, so only the dragged one moves.
  function currentWidths(): ColumnWidths {
    if (columnWidths.widths) return columnWidths.widths;
    return Object.fromEntries(
      WIDTH_KEYS.map((key) => [key, clampColumnWidth(headerCells.current[key]?.getBoundingClientRect().width ?? 0)]),
    );
  }

  function withWidth(base: ColumnWidths, key: string, width: number): ColumnWidths {
    return { ...base, [key]: clampColumnWidth(width) };
  }

  function startDrag(key: string, startX: number) {
    const base = currentWidths();
    const startWidth = base[key] ?? DEFAULT_COLUMN_WIDTH;
    let latest = base;
    function handleMove(event: MouseEvent) {
      latest = withWidth(base, key, startWidth + event.clientX - startX);
      columnWidths.showWidths(latest);
    }
    function handleUp() {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
      // A click without a drag shouldn't pin the automatic layout.
      if (latest !== base) columnWidths.saveWidths(latest);
    }
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
  }

  function stepWidth(key: string, step: number) {
    const base = currentWidths();
    columnWidths.saveWidths(withWidth(base, key, (base[key] ?? DEFAULT_COLUMN_WIDTH) + step));
  }

  function headerProps(key: string) {
    const width = columnWidths.widths ? (columnWidths.widths[key] ?? DEFAULT_COLUMN_WIDTH) : undefined;
    return {
      ref: (cell: HTMLTableCellElement | null) => {
        headerCells.current[key] = cell;
      },
      style: width === undefined ? undefined : { width },
    };
  }

  function resizer(key: string, label: string) {
    return (
      <ColumnResizer
        label={label}
        width={columnWidths.widths?.[key]}
        onDragStart={(startX) => startDrag(key, startX)}
        onStep={(step) => stepWidth(key, step)}
      />
    );
  }

  function handleSort(column: Column) {
    const isSameColumn = sort?.column === column.key;
    // Numbers start high-to-low (biggest movers first); tickers start A-Z.
    setSort({ column: column.key, isDescending: isSameColumn ? !sort.isDescending : column.isNumeric });
  }

  if (run.rows.length === 0) {
    return (
      <p className="empty-state">
        No stocks match this screen right now. Top-gainer screens fill up once pre-market opens at
        4:00 AM ET.
      </p>
    );
  }

  const rows = sort ? [...run.rows].sort((left, right) => compareRows(left, right, sort)) : run.rows;
  const savedWidths = columnWidths.widths;
  // Saved widths need a fixed layout, or the browser stretches columns back to fit their content.
  const tableStyle = savedWidths
    ? { width: WIDTH_KEYS.reduce((total, key) => total + (savedWidths[key] ?? DEFAULT_COLUMN_WIDTH), 0) }
    : undefined;

  return (
    <>
      <div className="results-meta">
        <p className="fetched-at">Fetched {new Date(run.fetched_at).toLocaleTimeString()}</p>
        {savedWidths && (
          <button type="button" className="button-quiet" onClick={columnWidths.resetWidths}>
            Reset column widths
          </button>
        )}
      </div>
      {columnWidths.error && (
        <p role="alert" className="alert">
          {columnWidths.error}
        </p>
      )}
      <div className="table-scroll">
      <table
        className={`data-table sticky-first-column${savedWidths ? " has-column-widths" : ""}`}
        style={tableStyle}
      >
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th key={column.key} className={column.isNumeric ? "number" : undefined} {...headerProps(column.key)}>
                <button
                  type="button"
                  className="sort-button"
                  data-active={sort?.column === column.key}
                  aria-label={`Sort by ${column.label}`}
                  onClick={() => handleSort(column)}
                >
                  {column.label}
                  {sort?.column === column.key && (sort.isDescending ? " ▼" : " ▲")}
                </button>
                {resizer(column.key, column.label)}
              </th>
            ))}
            {OTHER_HEADERS.map((header) => (
              <th key={header.key} className={header.isNumeric ? "number" : undefined} {...headerProps(header.key)}>
                {header.label}
                {resizer(header.key, header.label)}
              </th>
            ))}
            <th {...headerProps(ACTIONS_KEY)}>
              <span className="visually-hidden">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ticker}>
              <td>
                <StockLink ticker={row.ticker} onOpen={onOpenStock} />{" "}
                <a
                  className="small-link"
                  href={finvizQuoteUrl(row.ticker)}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Open ${row.ticker} on Finviz`}
                >
                  Finviz
                </a>
                <div className="company muted" title={row.company ?? undefined}>
                  {row.company ?? MISSING_VALUE}
                </div>
              </td>
              <td className="number">{formatNumber(row.price)}</td>
              <td className={`number ${changeClass(row.change_percent)}`}>
                {formatSignedPercent(row.change_percent)}
              </td>
              <td className={`number ${changeClass(row.after_hours_change_percent)}`}>
                {formatSignedPercent(row.after_hours_change_percent)}
              </td>
              <td className="number">{formatCount(row.volume)}</td>
              <td className="number">{formatNumber(row.relative_volume)}</td>
              <td className="number">{formatNumber(row.float_millions)}</td>
              <td className="number">{formatNumber(row.market_cap_millions)}</td>
              <td>
                {row.news_time && (
                  <span className="news-time muted">{formatNewsTime(row.news_time, new Date())}</span>
                )}
                {row.news_title && isWebUrl(row.news_url) ? (
                  <a className="headline" href={row.news_url} target="_blank" rel="noreferrer" title={row.news_title}>
                    {row.news_title}
                  </a>
                ) : (
                  <span className="headline">{row.news_title ?? MISSING_VALUE}</span>
                )}
              </td>
              <TopSetupCells setup={row.top_setup} ticker={row.ticker} />
              <td>
                <VerdictBadge verdict={row.verdict} />
              </td>
              <td>
                <div className="row-actions">
                  {watchlistTickers.has(row.ticker) ? (
                    <button type="button" disabled aria-label={`${row.ticker} is on the watchlist`}>
                      On watchlist
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onAddToWatchlist(row.ticker)}
                      aria-label={`Add ${row.ticker} to watchlist`}
                    >
                      + Watchlist
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </>
  );
}
