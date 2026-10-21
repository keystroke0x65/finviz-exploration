import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PatternStats } from "../api/trackRecord";
import { TrackRecordView } from "./TrackRecordView";

const fetchTrackRecord = vi.fn();
vi.mock("../api/trackRecord", () => ({
  fetchTrackRecord: (filters: unknown) => fetchTrackRecord(filters),
}));

function row(overrides: Partial<PatternStats> = {}): PatternStats {
  return {
    pattern: "bull_flag", timeframe: "5m", trades: 42, wins: 20, losses: 18, expired_after_fill: 4,
    win_rate: 20 / 42, average_r: 0.31, average_max_favorable_r: 1.8, not_trades: 7, still_open: 3, ...overrides,
  };
}

describe("TrackRecordView", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists each pattern's results", async () => {
    fetchTrackRecord.mockResolvedValue({ rows: [row()], min_trades: 30 });
    render(<TrackRecordView />);

    const bullFlag = await screen.findByRole("row", { name: /Bull flag/ });
    expect(within(bullFlag).getByText("42")).toBeInTheDocument();
    expect(within(bullFlag).getByText("48%")).toBeInTheDocument();
    expect(within(bullFlag).getByText("+0.31R")).toBeInTheDocument();
    expect(within(bullFlag).getByText("1.80R")).toBeInTheDocument();
  });

  it("marks patterns with too little history", async () => {
    fetchTrackRecord.mockResolvedValue({ rows: [row({ pattern: "abcd", trades: 12 })], min_trades: 30 });
    render(<TrackRecordView />);

    const abcd = await screen.findByRole("row", { name: /ABCD/ });
    expect(abcd).toHaveAttribute("data-thin", "true");
    expect(within(abcd).getByText("not enough history yet")).toBeInTheDocument();
  });

  it("refetches when a filter changes", async () => {
    fetchTrackRecord.mockResolvedValue({ rows: [row()], min_trades: 30 });
    render(<TrackRecordView />);
    await screen.findByRole("row", { name: /Bull flag/ });

    fireEvent.change(screen.getByLabelText("Float"), { target: { value: "under_5m" } });

    await vi.waitFor(() =>
      expect(fetchTrackRecord).toHaveBeenLastCalledWith({ timeframe: null, float_bucket: "under_5m", session: null }),
    );
  });

  it("explains an empty track record", async () => {
    fetchTrackRecord.mockResolvedValue({ rows: [], min_trades: 30 });
    render(<TrackRecordView />);

    expect(await screen.findByText(/No resolved setups yet/)).toBeInTheDocument();
  });
});
