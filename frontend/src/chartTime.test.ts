import { describe, expect, it } from "vitest";
import { toChartTime } from "./chartTime";

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
