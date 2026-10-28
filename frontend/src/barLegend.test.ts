import { describe, expect, it } from "vitest";
import { describeBar, formatVolume } from "./barLegend";

const BAR = { time: "2026-10-27T12:00:00-04:00", open: 1.07, high: 1.09, low: 1.06, close: 1.08, volume: 92_869 };

describe("formatVolume", () => {
  it("shortens thousands, millions and billions to one decimal", () => {
    expect(formatVolume(92_869)).toBe("92.9K");
    expect(formatVolume(1_234_567)).toBe("1.2M");
    expect(formatVolume(2_500_000_000)).toBe("2.5B");
  });

  it("keeps small volumes whole", () => {
    expect(formatVolume(718)).toBe("718");
    expect(formatVolume(0)).toBe("0");
  });
});

describe("describeBar", () => {
  it("labels an intraday bar with its market-time date and time", () => {
    expect(describeBar(BAR, false).time).toBe("Oct 27, 12:00 PM");
  });

  it("labels a daily bar with its date only", () => {
    expect(describeBar({ ...BAR, time: "2026-10-27T00:00:00-04:00" }, true).time).toBe("Oct 27, 2026");
  });

  it("formats prices, volume and the open-to-close change", () => {
    expect(describeBar(BAR, false)).toMatchObject({
      open: "1.07", high: "1.09", low: "1.06", close: "1.08", volume: "92.9K", change: "+0.93%",
      direction: "up",
    });
  });

  it("marks a bar that closed below its open as down", () => {
    expect(describeBar({ ...BAR, close: 1.06 }, false)).toMatchObject({ change: "-0.93%", direction: "down" });
  });

  it("treats a bar that closed at its open as up, like the candles do", () => {
    expect(describeBar({ ...BAR, close: 1.07 }, false)).toMatchObject({ change: "0.00%", direction: "up" });
  });
});
