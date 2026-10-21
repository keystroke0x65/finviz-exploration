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
});
