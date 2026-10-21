import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Verdict } from "../api/setups";
import { VerdictBadge } from "./VerdictBadge";

function verdict(computedAt: string): Verdict {
  return { call: "leans_long", score: 0.4, parts: {}, reasons: ["Above 5 of 5 trend lines"], computed_at: computedAt };
}

describe("VerdictBadge", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("says when the verdict was scored", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-21T16:00:00Z"));
    render(<VerdictBadge verdict={verdict("2026-10-21T15:30:00Z")} />);

    const badge = screen.getByText("Leans long");
    expect(badge.getAttribute("title")).toMatch(/^Scored /);
    expect(badge.getAttribute("title")).toContain("Above 5 of 5 trend lines");
    expect(badge).toHaveAttribute("data-stale", "false");
  });

  it("marks a verdict from an earlier day as stale", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-21T16:00:00Z"));
    render(<VerdictBadge verdict={verdict("2026-10-16T19:00:00Z")} />);

    expect(screen.getByText("Leans long")).toHaveAttribute("data-stale", "true");
  });
});
