import { describe, expect, it } from "vitest";
import type { ScanStatus } from "./api/setups";
import { describeScanStatus } from "./scanStatus";

const NOW = new Date("2026-10-26T15:50:00-04:00");
const COMPLETED_AT = "2026-10-26T15:45:00-04:00";

function status(overrides: Partial<ScanStatus> = {}): ScanStatus {
  return {
    latest: { status: "completed", finished_at: COMPLETED_AT, scanned: 40, failed: [] },
    last_completed_at: COMPLETED_AT,
    is_overdue: false,
    ...overrides,
  };
}

describe("describeScanStatus", () => {
  it("quietly notes a clean scan", () => {
    expect(describeScanStatus(status(), NOW)).toEqual({ isProblem: false, text: "Last scan 3:45 PM · 40 stocks" });
  });

  it("counts stocks a scan couldn't reach", () => {
    const partial = status({
      latest: { status: "completed", finished_at: COMPLETED_AT, scanned: 38, failed: [{ ticker: "BAD", reason: "x" }, { ticker: "WORSE", reason: "y" }] },
    });

    expect(describeScanStatus(partial, NOW)).toEqual({
      isProblem: false,
      text: "Last scan 3:45 PM · 38 stocks, 2 couldn't be scanned",
    });
  });

  it("flags a crashed scan and says how old the setups are", () => {
    const crashed = status({ latest: { status: "crashed", finished_at: "2026-10-26T15:15:00-04:00", error_type: "TypeError" }, last_completed_at: "2026-10-26T15:00:00-04:00" });

    expect(describeScanStatus(crashed, NOW)).toEqual({
      isProblem: true,
      text: "The 3:15 PM scan failed (TypeError), so these setups are from the 3:00 PM scan. Details are in the backend log.",
    });
  });

  it("flags a crash before any scan has completed", () => {
    const crashed = status({ latest: { status: "crashed", finished_at: "2026-10-26T15:15:00-04:00", error_type: "TypeError" }, last_completed_at: null });

    expect(describeScanStatus(crashed, NOW).text).toBe(
      "The 3:15 PM scan failed (TypeError) and no scan has completed yet. Details are in the backend log.",
    );
  });

  it("flags scans that have stopped running", () => {
    const stalled = status({ last_completed_at: "2026-10-26T15:00:00-04:00", is_overdue: true, latest: { status: "completed", finished_at: "2026-10-26T15:00:00-04:00", scanned: 40, failed: [] } });

    expect(describeScanStatus(stalled, NOW)).toEqual({
      isProblem: true,
      text: "No scan has finished since 3:00 PM; they should run every 15 minutes from 4 AM to 8 PM ET. These setups may be out of date.",
    });
  });

  it("dates a scan from an earlier day", () => {
    const friday = status({
      latest: { status: "completed", finished_at: "2026-10-23T19:45:00-04:00", scanned: 40, failed: [] },
      last_completed_at: "2026-10-23T19:45:00-04:00",
    });

    expect(describeScanStatus(friday, NOW).text).toBe("Last scan Oct 23, 7:45 PM · 40 stocks");
  });

  it("says when nothing has been scanned yet", () => {
    expect(describeScanStatus(status({ latest: null, last_completed_at: null }), NOW)).toEqual({
      isProblem: false,
      text: "No full scan yet",
    });
  });
});
