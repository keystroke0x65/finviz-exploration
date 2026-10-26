import { describe, expect, it } from "vitest";
import { barSession, toChartTime } from "./chartTime";

describe("toChartTime", () => {
  it("shifts by the Eastern offset in summer (EDT, UTC-4)", () => {
    expect(toChartTime("2026-07-01T14:00:00Z")).toBe(Date.UTC(2026, 6, 1, 10, 0) / 1000);
  });

  it("shifts by the Eastern offset in winter (EST, UTC-5)", () => {
    expect(toChartTime("2026-12-01T15:00:00Z")).toBe(Date.UTC(2026, 11, 1, 10, 0) / 1000);
  });

  it("accepts timestamps that carry an Eastern offset", () => {
    expect(toChartTime("2026-10-20T09:30:00-04:00")).toBe(Date.UTC(2026, 9, 20, 9, 30) / 1000);
  });
});

describe("barSession", () => {
  it("puts bars before 9:30 AM Eastern in pre-market", () => {
    expect(barSession("2026-10-20T04:00:00-04:00")).toBe("pre-market");
    expect(barSession("2026-10-20T09:29:00-04:00")).toBe("pre-market");
  });

  it("puts 9:30 AM to 3:59 PM Eastern in regular hours", () => {
    expect(barSession("2026-10-20T09:30:00-04:00")).toBe("regular");
    expect(barSession("2026-10-20T15:59:00-04:00")).toBe("regular");
  });

  it("puts 4 PM Eastern onwards in after-hours", () => {
    expect(barSession("2026-10-20T16:00:00-04:00")).toBe("after-hours");
    expect(barSession("2026-10-20T19:59:00-04:00")).toBe("after-hours");
  });

  it("uses Eastern time whatever the offset in the timestamp", () => {
    expect(barSession("2026-12-01T14:00:00Z")).toBe("pre-market"); // 9:00 AM EST
  });
});
