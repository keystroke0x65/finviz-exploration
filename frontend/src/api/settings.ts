import { jsonRequest, requestJson } from "./http";

export interface Settings {
  show_short_setups: boolean;
}

export function fetchSettings(): Promise<Settings> {
  return requestJson<Settings>("/api/settings");
}

export function saveSettings(settings: Settings): Promise<Settings> {
  return requestJson<Settings>("/api/settings", jsonRequest("PUT", settings));
}

// Pixel width per column key; empty means the table sizes its columns itself.
export type ColumnWidths = Record<string, number>;

export async function fetchScreenColumnWidths(): Promise<ColumnWidths> {
  const body = await requestJson<{ widths: ColumnWidths }>("/api/settings/screen-column-widths");
  return body.widths;
}

export async function saveScreenColumnWidths(widths: ColumnWidths): Promise<ColumnWidths> {
  const body = await requestJson<{ widths: ColumnWidths }>(
    "/api/settings/screen-column-widths",
    jsonRequest("PUT", { widths }),
  );
  return body.widths;
}

// Dollars; null means not set.
export interface JournalSettings {
  risk_per_trade: number | null;
  max_position: number | null;
  max_daily_loss: number | null;
}

export function fetchJournalSettings(): Promise<JournalSettings> {
  return requestJson<JournalSettings>("/api/settings/journal");
}

export function saveJournalSettings(settings: JournalSettings): Promise<JournalSettings> {
  return requestJson<JournalSettings>("/api/settings/journal", jsonRequest("PUT", settings));
}
