import { describe, expect, it } from "vitest";
import { firstCutoff, showMore } from "./newsWindow";

const NOW = new Date("2026-11-11T12:00:00Z");
const DAY_MS = 86_400_000;

function itemDaysAgo(days: number) {
  return { time: new Date(NOW.getTime() - days * DAY_MS).toISOString(), source: "Wire", title: `${days}d`, url: "https://x" };
}

describe("news window", () => {
  it("starts with the last 2 weeks", () => {
    expect(firstCutoff(NOW).toISOString()).toBe("2026-10-28T12:00:00.000Z");
  });

  it("shows the 2 weeks before on each click", () => {
    const next = showMore([itemDaysAgo(3), itemDaysAgo(20)], NOW, firstCutoff(NOW));

    expect(next?.cutoff.toISOString()).toBe("2026-10-14T12:00:00.000Z");
    expect(next?.skipped).toBeNull();
  });

  it("skips ahead past 2-week stretches with no news and says what it skipped", () => {
    const next = showMore([itemDaysAgo(3), itemDaysAgo(50)], NOW, firstCutoff(NOW));

    // 50 days ago falls in the 4th 2-week stretch (42-56 days back).
    expect(next?.cutoff.toISOString()).toBe(new Date(NOW.getTime() - 56 * DAY_MS).toISOString());
    expect(next?.skipped).toEqual({
      from: new Date(NOW.getTime() - 42 * DAY_MS),
      to: new Date(NOW.getTime() - 14 * DAY_MS),
    });
  });

  it("has nothing more once every item is shown", () => {
    expect(showMore([itemDaysAgo(3)], NOW, firstCutoff(NOW))).toBeNull();
  });
});
