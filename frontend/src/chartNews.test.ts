import { describe, expect, it } from "vitest";
import { newsByBarTime } from "./chartNews";
import { toChartTime } from "./chartTime";

const BAR_TIMES = ["2026-11-10T04:00:00-05:00", "2026-11-10T09:30:00-05:00", "2026-11-10T09:31:00-05:00"];
const bars = BAR_TIMES.map((time) => ({ time, open: 1, high: 1, low: 1, close: 1, volume: 1 }));

function news(time: string, title = "headline") {
  return { time, source: "Wire", title, url: "https://example.com" };
}

describe("newsByBarTime", () => {
  it("puts news on the bar it came out in", () => {
    const grouped = newsByBarTime([news("2026-11-10T09:30:40-05:00")], bars);

    expect([...grouped.keys()]).toEqual([toChartTime(BAR_TIMES[1])]);
  });

  it("puts news from before the day's first bar on that first bar", () => {
    const grouped = newsByBarTime([news("2026-11-10T01:30:00-05:00")], bars);

    expect([...grouped.keys()]).toEqual([toChartTime(BAR_TIMES[0])]);
  });

  it("groups news from the same bar", () => {
    const grouped = newsByBarTime([news("2026-11-10T09:31:05-05:00", "a"), news("2026-11-10T09:31:50-05:00", "b")], bars);

    expect(grouped.get(toChartTime(BAR_TIMES[2]))?.map((item) => item.title)).toEqual(["a", "b"]);
  });

  it("leaves out news from before the chart starts or after it ends", () => {
    const grouped = newsByBarTime([news("2026-11-09T15:00:00-05:00"), news("2026-11-11T08:00:00-05:00")], bars);

    expect(grouped.size).toBe(0);
  });

  it("puts weekend news on a daily chart's next trading day", () => {
    const daily = ["2026-11-06T00:00:00-05:00", "2026-11-09T00:00:00-05:00"].map((time) => ({
      time, open: 1, high: 1, low: 1, close: 1, volume: 1,
    }));

    const grouped = newsByBarTime([news("2026-11-08T10:00:00-05:00")], daily);

    expect([...grouped.keys()]).toEqual([toChartTime(daily[1].time)]);
  });
});
