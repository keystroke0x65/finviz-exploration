import { jsonRequest, requestJson } from "./http";

export type MarketCapOption =
  | "large_and_under"
  | "mid_and_under"
  | "small_and_under"
  | "micro_and_under"
  | "nano";

export interface ScreenForm {
  country?: "usa" | null;
  price_under?: number | null;
  float_under_millions?: number | null;
  market_cap?: MarketCapOption | null;
  volume_over_thousands?: number | null;
  relative_volume_over?: number | null;
}

export interface ScreenDraft {
  form: ScreenForm;
  extra_filters: string[];
  signal: string | null;
  order: string | null;
}

export interface ParsedScreenDraft extends ScreenDraft {
  ignored_params: string[];
}

export interface ScreenInput extends ScreenDraft {
  name: string;
  feeds_watchlist: boolean;
}

export interface Screen extends ScreenInput {
  id: number;
  finviz_url: string;
  created_at: string;
  updated_at: string;
}

export interface ScreenRow {
  ticker: string;
  company: string | null;
  country: string | null;
  market_cap_millions: number | null;
  float_millions: number | null;
  average_volume_thousands: number | null;
  relative_volume: number | null;
  price: number | null;
  change_percent: number | null;
  volume: number | null;
  after_hours_close: number | null;
  after_hours_change_percent: number | null;
  news_time: string | null; // ISO timestamp, Eastern offset
  news_url: string | null;
  news_title: string | null;
}

export interface ScreenRun {
  rows: ScreenRow[];
  fetched_at: string;
}

export type FormFieldName = keyof ScreenForm;

export interface FormFields {
  options: Record<FormFieldName, (string | number)[]>;
  signals: Record<string, string>;
}

export function listScreens(): Promise<Screen[]> {
  return requestJson<Screen[]>("/api/screens");
}

export function createScreen(input: ScreenInput): Promise<Screen> {
  return requestJson<Screen>("/api/screens", jsonRequest("POST", input));
}

export function updateScreen(id: number, input: ScreenInput): Promise<Screen> {
  return requestJson<Screen>(`/api/screens/${id}`, jsonRequest("PUT", input));
}

export function deleteScreen(id: number): Promise<void> {
  return requestJson<void>(`/api/screens/${id}`, { method: "DELETE" });
}

export function runScreen(id: number): Promise<ScreenRun> {
  return requestJson<ScreenRun>(`/api/screens/${id}/run`, { method: "POST" });
}

export function parseScreenerUrl(url: string): Promise<ParsedScreenDraft> {
  return requestJson<ParsedScreenDraft>("/api/screens/parse-url", jsonRequest("POST", { url }));
}

export function fetchFormFields(): Promise<FormFields> {
  return requestJson<FormFields>("/api/screens/form-fields");
}
