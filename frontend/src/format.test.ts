import { describe, expect, it } from "vitest";
import { formatDollars, formatNewsTime, formatSignedDollars } from "./format";

const NOW = new Date("2026-10-26T15:00:00-04:00");

describe("formatNewsTime", () => {
  it("shows the Eastern date and time without the year for this year's news", () => {
    expect(formatNewsTime("2026-10-22T11:00:00-04:00", NOW)).toBe("Oct 22, 11:00 AM");
  });

  it("adds the year for older news", () => {
    expect(formatNewsTime("2025-07-14T16:10:00-04:00", NOW)).toBe("Jul 14, 2025, 4:10 PM");
  });

  it("uses Eastern time whatever the viewer's timezone", () => {
    expect(formatNewsTime("2026-10-22T12:30:00Z", NOW)).toBe("Oct 22, 8:30 AM");
  });
});

describe("formatDollars", () => {
  it("formats dollars with a real minus sign and thousands separators", () => {
    expect(formatDollars(1150)).toBe("$1,150.00");
    expect(formatDollars(-170, 0)).toBe("−$170");
    expect(formatDollars(null)).toBe("—");
  });

  it("can show the sign of a gain", () => {
    expect(formatSignedDollars(50)).toBe("+$50.00");
    expect(formatSignedDollars(-12.5)).toBe("−$12.50");
    expect(formatSignedDollars(0)).toBe("$0.00");
  });
});
