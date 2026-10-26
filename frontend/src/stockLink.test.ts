import { describe, expect, it } from "vitest";
import { readTickerFromSearch, stockUrl } from "./stockLink";

describe("stockUrl", () => {
  it("points at the Stock view for a ticker", () => {
    expect(stockUrl("HOST")).toBe("/?stock=HOST");
  });

  it("escapes characters that mean something in a URL", () => {
    expect(stockUrl("BRK.B")).toBe("/?stock=BRK.B");
  });
});

describe("readTickerFromSearch", () => {
  it("reads the ticker, upper-cased", () => {
    expect(readTickerFromSearch("?stock=host")).toBe("HOST");
  });

  it("accepts class shares and dashes", () => {
    expect(readTickerFromSearch("?stock=BRK.B")).toBe("BRK.B");
    expect(readTickerFromSearch("?stock=BF-B")).toBe("BF-B");
  });

  it("ignores a missing, empty or malformed ticker", () => {
    expect(readTickerFromSearch("")).toBeNull();
    expect(readTickerFromSearch("?stock=")).toBeNull();
    expect(readTickerFromSearch("?stock=<script>")).toBeNull();
    expect(readTickerFromSearch("?stock=TOOLONGTICKER")).toBeNull();
  });
});
