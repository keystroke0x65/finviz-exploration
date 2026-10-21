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
