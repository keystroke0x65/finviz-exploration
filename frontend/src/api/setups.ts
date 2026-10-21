import { jsonRequest, requestJson } from "./http";

export type Direction = "long" | "short";
export type Timeframe = "1m" | "5m" | "daily";
export type SetupState = "forming" | "triggered" | "extended" | "invalidated";

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
}

export interface SetupsResponse {
  setups: Setup[];
  warnings: Setup[];
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
};

export const SCORE_PART_NAMES: Record<string, string> = {
  reward_risk: "Reward:risk",
  quality: "Pattern quality",
  volume: "Relative volume",
  freshness: "Freshness",
  timeframe_agreement: "Other timeframes agree",
  conflict: "Opposite pattern",
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
