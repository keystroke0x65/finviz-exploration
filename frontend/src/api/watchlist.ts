import { jsonRequest, requestJson } from "./http";
import type { Verdict } from "./setups";

export interface Appearance {
  seen_on: string;
  change_percent: number | null;
  screen_id: number;
}

export interface PriceSnapshot {
  price: number | null;
  change_percent: number | null;
  after_hours_change_percent: number | null;
  relative_volume: number | null;
  fetched_at: string;
}

export interface WatchlistEntry {
  ticker: string;
  source: "auto" | "manual";
  added_at: string;
  last_seen_in_feeder_at: string | null;
  is_pinned: boolean;
  expires_at: string | null;
  appearances: Appearance[];
  snapshot: PriceSnapshot | null;
  verdict: Verdict | null;
}

export interface FeederResult {
  screens_run: number;
  tickers_added: string[];
  tickers_updated: string[];
  tickers_expired: string[];
  failed_screens: { screen: string; reason: string }[];
}

export interface FeederStatus extends FeederResult {
  finished_at: string;
}

function entryPath(ticker: string): string {
  return `/api/watchlist/${encodeURIComponent(ticker)}`;
}

export function listWatchlist(): Promise<WatchlistEntry[]> {
  return requestJson<WatchlistEntry[]>("/api/watchlist");
}

export function addToWatchlist(ticker: string): Promise<WatchlistEntry> {
  return requestJson<WatchlistEntry>("/api/watchlist", jsonRequest("POST", { ticker }));
}

export function removeFromWatchlist(ticker: string): Promise<void> {
  return requestJson<void>(entryPath(ticker), { method: "DELETE" });
}

export function setPinned(ticker: string, isPinned: boolean): Promise<WatchlistEntry> {
  return requestJson<WatchlistEntry>(entryPath(ticker), jsonRequest("PATCH", { is_pinned: isPinned }));
}

export function refreshWatchlist(): Promise<FeederResult> {
  return requestJson<FeederResult>("/api/watchlist/refresh", { method: "POST" });
}

export function fetchFeederStatus(): Promise<FeederStatus | null> {
  return requestJson<FeederStatus | null>("/api/watchlist/feeder-status");
}
