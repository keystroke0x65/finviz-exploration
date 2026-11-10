import type { Bar } from "./bars";
import { jsonRequest, requestJson } from "./http";
import type { Direction, SlidingScale } from "./setups";

// Mirrors backend/app/journal/schemas.py.

export type JournalPeriod = "today" | "week" | "month" | "all";
export type EntryKind = "trade" | "pass";
export type FillSide = "buy" | "sell";
export type PlanFlag = "exited_before_target" | "held_past_stop" | "followed_plan";
export type PassOutcome = "target" | "stop" | "never_filled" | "undecided" | "not_scored";
export type BarDayStatus = "partial" | "complete" | "missing" | "incomplete";

export interface Fill {
  side: FillSide;
  time: string;
  price: number;
  shares: number;
}

export interface TradeDraft {
  kind: "trade";
  ticker: string;
  direction: Direction;
  setup_record_id: number | null;
  plan_stop: number | null;
  plan_target: number | null;
  fees: number;
  mistakes: string[];
  note: string;
  fills: Fill[];
}

export interface PassDraft {
  kind: "pass";
  ticker: string;
  direction: Direction;
  setup_record_id: number | null;
  reasons: string[];
  note: string;
  decided_at: string | null;
}

export type EntryDraft = TradeDraft | PassDraft;

export interface TradeFigures {
  status: "open" | "closed";
  first_price: number;
  average_entry: number;
  average_exit: number | null;
  shares_held: number;
  max_shares: number;
  money_in: number;
  total_bought: number;
  realised_pnl: number;
  closed_pnl: { time: string; pnl: number }[];
  fees: number;
  net_pnl: number;
  r_multiple: number | null;
  planned_reward_risk: number | null;
  opened_at: string;
  last_fill_at: string;
  duration_seconds: number;
}

export interface SetupSnapshot {
  setup_record_id: number | null;
  pattern: string;
  timeframe: string;
  direction: string;
  entry: number;
  stop: number;
  target: number;
  reward_risk: number;
  score: number;
  state: string;
  verdict: string | null;
  sliding_scale: SlidingScale | null;
}

export interface StockFacts {
  company: string | null;
  country: string | null;
  sector: string | null;
  industry: string | null;
  market_cap_millions: number | null;
  float_millions: number | null;
  price: number | null;
  change_percent: number | null;
  volume_so_far: number | null;
  volume_vs_average: number | null;
}

export interface AfterExit {
  best_r: number | null;
  worst_r: number | null;
  best_price: number | null;
  worst_price: number | null;
}

export interface JournalEntry {
  id: number;
  kind: EntryKind;
  ticker: string;
  direction: Direction;
  created_at: string;
  updated_at: string;
  decided_at: string;
  setup: SetupSnapshot | null;
  stock: StockFacts;
  plan_stop: number | null;
  plan_target: number | null;
  fees: number;
  reasons: string[];
  mistakes: string[];
  note: string;
  pass_price: number | null;
  fills: Fill[];
  figures: TradeFigures | null;
  after_exit: AfterExit | null;
  plan_flags: PlanFlag[];
  pass_score: { outcome: PassOutcome; r: number | null } | null;
  bar_warning: string | null;
}

export interface Preview {
  figures: TradeFigures | null;
  error: string | null;
}

export interface ReasonItem {
  key: string;
  label: string;
}

export interface ReasonCatalog {
  pass_reasons: { group: string; items: ReasonItem[] }[];
  mistakes: ReasonItem[];
}

export interface EntryBars {
  bars: Bar[];
  days: { day: string; status: BarDayStatus | null }[];
}

export interface DaySetup {
  setup_record_id: number;
  pattern: string;
  timeframe: string;
  direction: string;
  entry: number;
  stop: number;
  target: number;
  reward_risk: number;
  score: number;
  state: string;
  verdict: string | null;
  sliding_scale: SlidingScale | null;
  outcome: string;
}

export interface Bucket {
  label: string;
  count: number;
  pnl: number;
}

export interface PassReasonRow {
  reason: string;
  count: number;
  target: number;
  stop: number;
  never_filled: number;
  undecided: number;
  average_r: number | null;
}

export interface VersusRow {
  pattern: string;
  timeframe: string;
  trades: number;
  win_rate: number | null;
  average_r: number | null;
  system: { trades: number; win_rate: number | null; average_r: number | null } | null;
  system_has_enough_history: boolean;
}

export interface JournalSummary {
  net_pnl: number;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  average_gain: number | null;
  average_loss: number | null;
  largest_win: number | null;
  largest_loss: number | null;
  average_planned_reward_risk: number | null;
  average_r: number | null;
  average_duration_seconds: number | null;
  average_sykes_points: number | null;
  average_sykes_letter: string | null;
  average_score: number | null;
  average_left_on_table_r: number | null;
  passes: number;
  open_trades: number;
  pnl_points: { time: string; pnl: number; cumulative: number }[];
  by_country: Bucket[];
  by_industry: Bucket[];
  by_pattern: Bucket[];
  by_mistake: Bucket[];
  by_time_of_day: Bucket[];
  by_duration: Bucket[];
  pass_reasons: PassReasonRow[];
  versus_system: VersusRow[];
}

export type DailyLossLevel = "ok" | "warning" | "reached";

export interface DailyLoss {
  realised_pnl_today: number;
  max_daily_loss: number | null;
  level: DailyLossLevel;
}

const BASE = "/api/journal";

export function fetchReasons(): Promise<ReasonCatalog> {
  return requestJson<ReasonCatalog>(`${BASE}/reasons`);
}

export function fetchEntries(kind: EntryKind | null, period: JournalPeriod): Promise<JournalEntry[]> {
  const kindQuery = kind ? `&kind=${kind}` : "";
  return requestJson<JournalEntry[]>(`${BASE}/entries?period=${period}${kindQuery}`);
}

export function fetchEntry(id: number): Promise<JournalEntry> {
  return requestJson<JournalEntry>(`${BASE}/entries/${id}`);
}

export function createEntry(draft: EntryDraft): Promise<JournalEntry> {
  return requestJson<JournalEntry>(`${BASE}/entries`, jsonRequest("POST", draft));
}

export function updateEntry(id: number, draft: EntryDraft): Promise<JournalEntry> {
  return requestJson<JournalEntry>(`${BASE}/entries/${id}`, jsonRequest("PUT", draft));
}

export function deleteEntry(id: number): Promise<void> {
  return requestJson<void>(`${BASE}/entries/${id}`, { method: "DELETE" });
}

export function previewTrade(draft: TradeDraft): Promise<Preview> {
  return requestJson<Preview>(`${BASE}/preview`, jsonRequest("POST", draft));
}

export function fetchEntryBars(id: number, interval: "1m" | "5m"): Promise<EntryBars> {
  return requestJson<EntryBars>(`${BASE}/entries/${id}/bars?interval=${interval}`);
}

export function fetchDaySetups(ticker: string, day: string, at: string): Promise<DaySetup[]> {
  const query = new URLSearchParams({ day, at }).toString();
  return requestJson<DaySetup[]>(`${BASE}/setups/${encodeURIComponent(ticker)}?${query}`);
}

export function fetchOpenTrade(ticker: string): Promise<JournalEntry | null> {
  return requestJson<JournalEntry | null>(`${BASE}/open-trade/${encodeURIComponent(ticker)}`);
}

export function fetchSummary(period: JournalPeriod): Promise<JournalSummary> {
  return requestJson<JournalSummary>(`${BASE}/summary?period=${period}`);
}

export function fetchDailyLoss(): Promise<DailyLoss> {
  return requestJson<DailyLoss>(`${BASE}/daily-loss`);
}

export function exportUrl(kind: "entries" | "fills", period: JournalPeriod): string {
  return `${BASE}/export/${kind}.csv?period=${period}`;
}
