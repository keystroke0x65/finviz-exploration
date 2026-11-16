import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DaySetup } from "../api/journal";
import { SetupPicker } from "./SetupPicker";

function daySetup(id: number, changes: Partial<DaySetup> = {}): DaySetup {
  return {
    setup_record_id: id, detected_at: "2026-11-16T09:20:00-05:00", triggered_at: "2026-11-16T09:44:00-05:00",
    pattern: "bull_flag", timeframe: "5m", direction: "long", entry: 0.76, stop: 0.74, target: 0.82, reward_risk: 3,
    score: 89, state: "triggered", verdict: null, sliding_scale: { letter: "C", points: 8, factors: [] }, outcome: "open",
    ...changes,
  };
}

describe("SetupPicker", () => {
  afterEach(cleanup);

  it("puts the matches first and the day's other setups after, each told apart by entry and trigger", () => {
    render(
      <SetupPicker
        ticker="RAIN"
        setups={{ matches: [daySetup(1)], others: [daySetup(2, { pattern: "abcd", entry: 0.9, triggered_at: null, state: "forming" })] }}
        selectedId={1}
        matchLabel="Best matches for your 9:45 AM buy at 0.76"
        selectedFallback={null}
        error={null}
        onChange={vi.fn()}
      />,
    );

    const best = screen.getByRole("group", { name: "Best matches for your 9:45 AM buy at 0.76" });
    expect(within(best).getByRole("option", { name: "Bull flag 5m · entry 0.7600 · triggered 9:44 AM · score 89 · Sykes C" }))
      .toBeInTheDocument();
    const rest = screen.getByRole("group", { name: "Other RAIN setups today (1)" });
    expect(within(rest).getByRole("option", { name: "ABCD 5m · entry 0.9000 · forming · score 89 · Sykes C" })).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("1");
  });

  it("reports the chosen setup, or none", () => {
    const onChange = vi.fn();
    render(<SetupPicker ticker="RAIN" setups={{ matches: [daySetup(1)], others: [] }} selectedId={1} matchLabel="x" selectedFallback={null} error={null} onChange={onChange} />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "" } });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "1" } });

    expect(onChange.mock.calls).toEqual([[null], [1]]);
  });

  it("says when the setups are still loading", () => {
    render(<SetupPicker ticker="RAIN" setups={null} selectedId={null} matchLabel="x" selectedFallback={null} error={null} onChange={vi.fn()} />);

    expect(screen.getByRole("option", { name: "Loading setups…" })).toBeInTheDocument();
  });
});
