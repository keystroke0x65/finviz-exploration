import { requestJson } from "./http";
import type { Timeframe } from "./setups";

export type FloatBucket = "under_5m" | "5m_to_10m" | "10m_to_20m" | "20m_to_50m" | "over_50m" | "unknown";
export type SessionName = "pre-market" | "regular" | "after-hours" | "daily";

export interface PatternStats {
  pattern: string;
  timeframe: string;
  trades: number;
  wins: number;
  losses: number;
  expired_after_fill: number;
  win_rate: number | null;
  average_r: number | null;
  average_max_favorable_r: number | null;
  not_trades: number;
  still_open: number;
}

export interface TrackRecordFilters {
  timeframe: Timeframe | null;
  float_bucket: FloatBucket | null;
  session: SessionName | null;
}

export interface TrackRecordResponse {
  rows: PatternStats[];
  min_trades: number;
}

export function fetchTrackRecord(filters: TrackRecordFilters): Promise<TrackRecordResponse> {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(filters)) {
    if (value) query.set(name, value);
  }
  const suffix = query.toString() ? `?${query}` : "";
  return requestJson<TrackRecordResponse>(`/api/track-record${suffix}`);
}
