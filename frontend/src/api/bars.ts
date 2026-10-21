import { requestJson } from "./http";
import type { Timeframe } from "./setups";

export interface Bar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SessionLevels {
  premarket_high: number | null;
  premarket_low: number | null;
  day_high: number | null;
  day_low: number | null;
  opening_range_high: number | null;
  opening_range_low: number | null;
  previous_close: number | null;
}

export interface BarsResponse {
  bars: Bar[];
  fetched_at: string;
  daily_levels: { price: number; touches: number }[];
  session: SessionLevels | null;
  vwap: (number | null)[] | null;
}

export function fetchBars(ticker: string, interval: Timeframe): Promise<BarsResponse> {
  return requestJson<BarsResponse>(`/api/bars/${encodeURIComponent(ticker)}?interval=${interval}`);
}
