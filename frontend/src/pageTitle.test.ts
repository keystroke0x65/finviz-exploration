import { afterEach, describe, expect, it } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";
import {
  journalTitle,
  screensTitle,
  setupsTitle,
  stockTitle,
  trackRecordTitle,
  useDocumentTitle,
  watchlistTitle,
} from "./pageTitle";

describe("page titles", () => {
  afterEach(cleanup);

  it("leads a stock tab with the ticker, price and change", () => {
    expect(stockTitle("HOST", { Ticker: "HOST", Price: "2.15", Change: "12.30%" })).toBe("HOST 2.15 +12.30% · Finviz");
    expect(stockTitle("HOST", { Ticker: "HOST", Price: "2.15", Change: "-0.57%" })).toBe("HOST 2.15 −0.57% · Finviz");
  });

  it("shows just the ticker until the quote arrives", () => {
    expect(stockTitle("HOST", null)).toBe("HOST · Finviz");
    expect(stockTitle(null, null)).toBe("Stock · Finviz");
  });

  it("shows the setup count, or the scan's progress while scanning", () => {
    expect(setupsTitle(12, null)).toBe("Setups · 12 · Finviz");
    expect(setupsTitle(null, null)).toBe("Setups · Finviz");
    expect(setupsTitle(12, { running: true, kind: "automatic", phase: "scanning", done: 12, total: 40, ticker: "HOST", started_at: "x" }))
      .toBe("Scanning 12/40 · Finviz");
    expect(setupsTitle(12, { running: true, kind: "manual", phase: "preparing", done: 0, total: 0, ticker: null, started_at: "x" }))
      .toBe("Scanning… · Finviz");
  });

  it("names the screen, the watchlist size, the journal's P&L and track record", () => {
    expect(screensTitle("Top gainers — low float")).toBe("Screens · Top gainers — low float · Finviz");
    expect(screensTitle(null)).toBe("Screens · Finviz");
    expect(watchlistTitle(63)).toBe("Watchlist · 63 stocks · Finviz");
    expect(journalTitle(25.5, "week")).toBe("Journal · +$25.50 this week · Finviz");
    expect(journalTitle(-12, "today")).toBe("Journal · −$12.00 today · Finviz");
    expect(journalTitle(null, "all")).toBe("Journal · Finviz");
    expect(trackRecordTitle()).toBe("Track record · Finviz");
  });

  it("sets the browser tab's title", () => {
    renderHook(() => useDocumentTitle("HOST 2.15 +12.30% · Finviz"));

    expect(document.title).toBe("HOST 2.15 +12.30% · Finviz");
  });
});
