import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { passEntry, tradeEntry } from "../test/journalFixtures";
import { JournalEntryDetail } from "./JournalEntryDetail";

const api = vi.hoisted(() => ({
  fetchEntryBars: vi.fn(),
  deleteEntry: vi.fn(),
  fetchDaySetups: vi.fn(),
  chartProps: [] as { markers?: unknown[]; levels: { price: number; kind: string }[] }[],
}));
vi.mock("../api/journal", () => ({
  fetchEntryBars: (...args: unknown[]) => api.fetchEntryBars(...args),
  deleteEntry: (id: number) => api.deleteEntry(id),
  fetchDaySetups: (...args: unknown[]) => api.fetchDaySetups(...args),
}));
vi.mock("./CandleChart", () => ({
  CandleChart: (props: { markers?: unknown[]; levels: { price: number; kind: string }[] }) => {
    api.chartProps.push(props);
    return <div data-testid="chart" />;
  },
}));
vi.mock("./TradePanel", () => ({ TradePanel: () => <section aria-label="edit trade" /> }));
vi.mock("./PassPanel", () => ({ PassPanel: () => <section aria-label="edit pass" /> }));

const BAR = { time: "2026-11-09T09:45:00-05:00", open: 1.8, high: 1.86, low: 1.79, close: 1.84, volume: 1000 };
const LABELS = { low_sykes: "Low Sykes grade", too_late: "Too late / extended", chased: "Chased" };

function renderDetail(entry = tradeEntry(), onChanged = vi.fn(), onDeleted = vi.fn()) {
  render(<JournalEntryDetail entry={entry} labels={LABELS} settings={null} onChanged={onChanged} onDeleted={onDeleted} />);
  return { onChanged, onDeleted };
}

describe("JournalEntryDetail", () => {
  beforeEach(() => {
    api.fetchEntryBars.mockResolvedValue({ bars: [BAR], days: [{ day: "2026-11-09", status: "complete" }] });
    api.fetchDaySetups.mockResolvedValue([]);
    api.chartProps = [];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("draws the saved chart with every fill and the plan", async () => {
    renderDetail();

    await screen.findByTestId("chart");
    const props = api.chartProps[api.chartProps.length - 1];
    expect(props.markers).toHaveLength(2);
    expect(props.levels).toEqual(expect.arrayContaining([
      expect.objectContaining({ price: 1.76, kind: "stop" }),
      expect.objectContaining({ price: 2.08, kind: "target" }),
    ]));
    expect(api.fetchEntryBars).toHaveBeenCalledWith(3, "1m");
  });

  it("says which days Finviz no longer has", async () => {
    api.fetchEntryBars.mockResolvedValue({ bars: [], days: [{ day: "2026-10-03", status: "missing" }] });

    renderDetail();

    expect(await screen.findByText("Bars for Oct 3 are no longer available from Finviz.")).toBeInTheDocument();
  });

  it("says when only part of a day was saved before Finviz dropped it", async () => {
    api.fetchEntryBars.mockResolvedValue({ bars: [BAR], days: [{ day: "2026-10-03", status: "incomplete" }] });

    renderDetail();

    expect(await screen.findByText("Bars for Oct 3 are only partly saved; Finviz no longer has the rest.")).toBeInTheDocument();
  });

  it("shows what happened after the exit and the plan check", async () => {
    renderDetail();

    expect(await screen.findByText("Kept going +1.40R after you sold")).toBeInTheDocument();
    expect(screen.getByText("Exited before target")).toBeInTheDocument();
    expect(screen.getByText("Chased")).toBeInTheDocument();
  });

  it("shows a pass's reasons and what the setup would have done", async () => {
    renderDetail(passEntry());

    expect(await screen.findByText("Low Sykes grade")).toBeInTheDocument();
    expect(screen.getByText("Would have stopped out (−1.00R)")).toBeInTheDocument();
  });

  it("deletes only after confirming", async () => {
    api.deleteEntry.mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const { onDeleted } = renderDetail();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(api.deleteEntry).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await vi.waitFor(() => expect(onDeleted).toHaveBeenCalledWith(3));
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it("opens the trade for editing", async () => {
    renderDetail();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(await screen.findByRole("region", { name: "edit trade" })).toBeInTheDocument();
  });
});
