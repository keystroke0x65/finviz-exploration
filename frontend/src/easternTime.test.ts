import { describe, expect, it } from "vitest";
import { easternIso, easternParts } from "./easternTime";

describe("eastern time", () => {
  it("turns an Eastern date and time into an ISO time with the right offset", () => {
    expect(easternIso("2026-11-09", "09:45")).toBe("2026-11-09T09:45:00-05:00");
    expect(easternIso("2026-07-15", "16:01")).toBe("2026-07-15T16:01:00-04:00");
  });

  it("splits any ISO time into its Eastern date and time", () => {
    expect(easternParts("2026-11-09T14:45:00Z")).toEqual({ date: "2026-11-09", time: "09:45" });
    expect(easternParts("2026-07-15T20:01:30Z")).toEqual({ date: "2026-07-15", time: "16:01" });
  });
});
