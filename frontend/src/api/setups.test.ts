import { describe, expect, it } from "vitest";
import { patternName } from "./setups";

describe("patternName", () => {
  it("names the new patterns", () => {
    expect(patternName("ascending_triangle")).toBe("Ascending triangle");
    expect(patternName("double_bottom")).toBe("Double bottom");
    expect(patternName("abcd")).toBe("ABCD");
    expect(patternName("inverse_abcd")).toBe("Inverse ABCD");
    expect(patternName("micro_pullback")).toBe("Micro pullback");
    expect(patternName("first_pullback")).toBe("First pullback");
    expect(patternName("first_bounce_fail")).toBe("First bounce fail");
  });

  it("names the milestone 3 patterns", () => {
    expect(patternName("bull_pennant")).toBe("Bull pennant");
    expect(patternName("symmetrical_triangle_up")).toBe("Symmetrical triangle (up)");
    expect(patternName("falling_wedge")).toBe("Falling wedge");
    expect(patternName("range_breakout")).toBe("Range breakout");
    expect(patternName("cup_and_handle")).toBe("Cup and handle");
    expect(patternName("inverse_head_and_shoulders")).toBe("Inverse head and shoulders");
    expect(patternName("triple_top")).toBe("Triple top");
    expect(patternName("rounding_bottom")).toBe("Rounding bottom");
  });
});
