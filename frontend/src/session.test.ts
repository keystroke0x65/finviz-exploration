import { describe, expect, it } from "vitest";
import { getMarketSession } from "./session";

describe("getMarketSession", () => {
  it.each([
    ["2026-10-20T07:59:00Z", "closed"], // 3:59 AM ET
    ["2026-10-20T08:00:00Z", "pre-market"], // 4:00 AM ET
    ["2026-10-20T13:29:00Z", "pre-market"], // 9:29 AM ET
    ["2026-10-20T13:30:00Z", "regular"], // 9:30 AM ET
    ["2026-10-20T19:59:00Z", "regular"], // 3:59 PM ET
    ["2026-10-20T20:00:00Z", "after-hours"], // 4:00 PM ET
    ["2026-10-20T23:59:00Z", "after-hours"], // 7:59 PM ET
    ["2026-10-21T00:00:00Z", "closed"], // 8:00 PM ET
    ["2026-10-24T15:00:00Z", "closed"], // Saturday 11 AM ET
    ["2026-11-02T14:30:00Z", "regular"], // 9:30 AM EST, after DST ends
    ["2026-11-02T13:30:00Z", "pre-market"], // 8:30 AM EST
  ])("at %s the session is %s", (isoTime, expectedPhase) => {
    expect(getMarketSession(new Date(isoTime)).phase).toBe(expectedPhase);
  });

  it("reports minutes since midnight Eastern for placing the now marker", () => {
    expect(getMarketSession(new Date("2026-10-20T14:15:00Z")).minutesSinceMidnight).toBe(10 * 60 + 15);
  });

  it("says when the current session ends", () => {
    expect(getMarketSession(new Date("2026-10-20T12:00:00Z")).nextChange).toBe("Regular hours open at 9:30 AM ET");
    expect(getMarketSession(new Date("2026-10-20T21:00:00Z")).nextChange).toBe("After-hours ends at 8:00 PM ET");
  });

  it("points to the next weekday pre-market when closed", () => {
    expect(getMarketSession(new Date("2026-10-21T03:00:00Z")).nextChange).toBe("Pre-market opens at 4:00 AM ET");
    expect(getMarketSession(new Date("2026-10-24T15:00:00Z")).nextChange).toBe("Pre-market opens Monday at 4:00 AM ET");
  });
});
