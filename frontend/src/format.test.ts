import { describe, expect, it } from "vitest";
import { formatNewsTime } from "./format";

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
