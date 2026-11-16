import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { RunningScan } from "../api/setups";
import { ScanProgressBar } from "./ScanProgressBar";

const SCANNING: RunningScan = {
  running: true, kind: "manual", phase: "scanning", done: 12, total: 40, ticker: "HOST",
  started_at: "2026-11-16T09:41:00-05:00",
};

describe("ScanProgressBar", () => {
  afterEach(cleanup);

  it("shows how many stocks are done, the one being scanned and when it started", () => {
    render(<ScanProgressBar progress={SCANNING} />);

    const bar = screen.getByRole("progressbar", { name: "Scanning watchlist" });
    expect(bar).toHaveAttribute("aria-valuenow", "12");
    expect(bar).toHaveAttribute("aria-valuemax", "40");
    expect(screen.getByText("12 of 40 stocks · HOST · started 9:41 AM")).toBeInTheDocument();
  });

  it("names an automatic scan", () => {
    render(<ScanProgressBar progress={{ ...SCANNING, kind: "automatic" }} />);

    expect(screen.getByRole("progressbar", { name: "Automatic scan" })).toBeInTheDocument();
  });

  it("says when the scan is preparing or finishing", () => {
    const { rerender } = render(<ScanProgressBar progress={{ ...SCANNING, phase: "preparing", done: 0, total: 0, ticker: null }} />);
    expect(screen.getByText("Preparing… · started 9:41 AM")).toBeInTheDocument();

    rerender(<ScanProgressBar progress={{ ...SCANNING, phase: "finishing", done: 40, ticker: null }} />);
    expect(screen.getByText("Finishing… · started 9:41 AM")).toBeInTheDocument();
  });
});
