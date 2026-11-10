import { describe, expect, it } from "vitest";
import { suggestShares } from "./positionSize";

describe("suggestShares", () => {
  it("sizes the position so the stop loses the risk amount", () => {
    expect(suggestShares(50, 1.84, 1.76, null)).toBe(625);
  });

  it("is capped by the largest position allowed", () => {
    expect(suggestShares(50, 1.84, 1.76, 1000)).toBe(543);
  });

  it("works for shorts with the stop above entry", () => {
    expect(suggestShares(50, 2.0, 2.1, null)).toBe(500);
  });

  it("is zero when entry and stop are the same", () => {
    expect(suggestShares(50, 2.0, 2.0, null)).toBe(0);
  });
});
