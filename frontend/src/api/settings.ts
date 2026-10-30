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
