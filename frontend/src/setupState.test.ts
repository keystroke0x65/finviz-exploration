import { describe, expect, it } from "vitest";
import { describeSetupState } from "./setupState";

describe("describeSetupState", () => {
  it("names a forming setup without a time", () => {
    expect(describeSetupState({ state: "forming", triggered_at: null, timeframe: "1m" })).toBe("Forming");
  });

  it("gives the Eastern time an intraday setup triggered", () => {
    expect(describeSetupState({ state: "triggered", triggered_at: "2026-10-20T13:42:00Z", timeframe: "1m" })).toBe(
      "Triggered 9:42 AM",
    );
  });

  it("gives the trigger time for an extended setup too", () => {
    expect(describeSetupState({ state: "extended", triggered_at: "2026-10-20T19:05:00Z", timeframe: "5m" })).toBe(
      "Extended, triggered 3:05 PM",
    );
  });

  it("gives the date a daily setup triggered", () => {
    expect(
      describeSetupState({ state: "triggered", triggered_at: "2026-10-20T13:42:00Z", timeframe: "daily" }),
    ).toBe("Triggered Oct 20");
  });

  it("falls back to the plain name when the trigger time is unknown", () => {
    expect(describeSetupState({ state: "triggered", triggered_at: null, timeframe: "1m" })).toBe("Triggered");
  });
});
