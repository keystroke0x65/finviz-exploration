import { jsonRequest, requestJson } from "./http";

export type Direction = "long" | "short";
export type Timeframe = "1m" | "5m" | "daily";
export type SetupState = "forming" | "triggered" | "extended" | "invalidated";

export type VerdictCall = "leans_long" | "leans_short" | "no_clear_edge";

export interface Verdict {
  call: VerdictCall;
  score: number;
  parts: Record<string, number>;
  reasons: string[];
  computed_at: string;
}

export interface Setup {
  id: number;
  ticker: string;
  pattern: string;
  direction: Direction;
  timeframe: Timeframe;
  entry: number;
  stop: number;
  capped_target: number;
  target_3r: number;
  available_reward_risk: number;
  risk_percent: number;
  blocking_level: number | null;
  partial_1r: number;
  partial_2r: number;
  trailing_stop: number | null;
  quality: number;
  score: number;
  score_parts: Record<string, number>;
  key_points: [string, number][];
  state: SetupState;
  session: string;
  detected_at: string;
  last_seen_at: string;
  has_conflict: boolean;
  verdict?: Verdict | null;
  track_record?: TrackRecordSummary | null;
}

export interface TrackRecordSummary {
  trades: number;
  win_rate: number | null;
  average_r: number | null;
  average_win_r: number | null;
  tickers: number;
  trading_days: number;
  has_enough_history: boolean;
}

// History counts in scores at this many trades over this many trading days. The backend
// decides (has_enough_history); these mirror it only for the explanatory text.
export const MIN_TRADES_FOR_TRACK_RECORD = 30;
export const MIN_TRADING_DAYS_FOR_TRACK_RECORD = 5;

// A bearish pattern shown while short setups are off: no stop, targets or R:R.
export interface Warning {
  id: number;
  ticker: string;
  pattern: string;
  direction: Direction;
  timeframe: Timeframe;
  entry: number;
  state: SetupState;
  key_points: [string, number][];
  detected_at: string;
  last_seen_at: string;
  verdict?: Verdict | null;
}

export function isTradeSetup(item: Setup | Warning): item is Setup {
  return "stop" in item;
}

export interface SetupsResponse {
  setups: Setup[];
  warnings: Warning[];
  show_short_setups: boolean;
}

export interface ScanResult {
  scanned: string[];
  failed: { ticker: string; reason: string }[];
  setups_found: number;
  scanned_at: string;
}

export const PATTERN_NAMES: Record<string, string> = {
  high_of_day_break: "High-of-day break",
  low_of_day_break: "Low-of-day break",
  premarket_high_break: "Pre-market high break",
  premarket_low_break: "Pre-market low break",
  opening_range_breakout: "Opening range breakout",
  opening_range_breakdown: "Opening range breakdown",
  red_to_green: "Red to green",
  green_to_red: "Green to red",
  vwap_reclaim: "VWAP reclaim",
  vwap_rejection: "VWAP rejection",
  bull_flag: "Bull flag",
  bear_flag: "Bear flag",
  flat_top_breakout: "Flat-top breakout",
  flat_bottom_breakdown: "Flat-bottom breakdown",
  ascending_triangle: "Ascending triangle",
  descending_triangle: "Descending triangle",
  double_bottom: "Double bottom",
  double_top: "Double top",
  abcd: "ABCD",
  inverse_abcd: "Inverse ABCD",
  micro_pullback: "Micro pullback",
  first_pullback: "First pullback",
  first_bounce_fail: "First bounce fail",
  bull_pennant: "Bull pennant",
  bear_pennant: "Bear pennant",
  symmetrical_triangle_up: "Symmetrical triangle (up)",
  symmetrical_triangle_down: "Symmetrical triangle (down)",
  falling_wedge: "Falling wedge",
  rising_wedge: "Rising wedge",
  range_breakout: "Range breakout",
  range_breakdown: "Range breakdown",
  cup_and_handle: "Cup and handle",
  inverted_cup_and_handle: "Inverted cup and handle",
  head_and_shoulders: "Head and shoulders",
  inverse_head_and_shoulders: "Inverse head and shoulders",
  triple_bottom: "Triple bottom",
  triple_top: "Triple top",
  rounding_bottom: "Rounding bottom",
  rounding_top: "Rounding top",
};

export const SCORE_PART_NAMES: Record<string, string> = {
  reward_risk: "Reward:risk",
  quality: "Pattern quality",
  volume: "Relative volume",
  freshness: "Freshness",
  timeframe_agreement: "Other timeframes agree",
  conflict: "Opposite pattern",
  track_record: "Track record",
  candles: "Candlestick at a key level",
};

export function patternName(pattern: string): string {
  return PATTERN_NAMES[pattern] ?? pattern.replace(/_/g, " ");
}

export function fetchSetups(): Promise<SetupsResponse> {
  return requestJson<SetupsResponse>("/api/setups");
}

export function fetchStockSetups(ticker: string): Promise<SetupsResponse> {
  return requestJson<SetupsResponse>(`/api/stocks/${encodeURIComponent(ticker)}/setups`);
}

export function runScan(ticker?: string): Promise<ScanResult> {
  return requestJson<ScanResult>("/api/scans", jsonRequest("POST", ticker ? { ticker } : {}));
}

export function fetchStockVerdict(ticker: string): Promise<Verdict | null> {
  return requestJson<Verdict | null>(`/api/stocks/${encodeURIComponent(ticker)}/verdict`);
}
