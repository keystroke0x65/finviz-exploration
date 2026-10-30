import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Screen } from "../api/screens";
import { ScreensView } from "./ScreensView";

const SCREEN: Screen = {
  id: 1, name: "Top gainers — low float", form: { country: "usa" }, extra_filters: [],
  signal: "ta_topgainers", order: "-change", feeds_watchlist: true,
  finviz_url: "https://elite.finviz.com/screener.ashx?v=111&f=geo_usa", created_at: "", updated_at: "",
};

const api = {
  listScreens: vi.fn(), fetchFormFields: vi.fn(), runScreen: vi.fn(), deleteScreen: vi.fn(),
};
vi.mock("../api/screens", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/screens")>()),
  listScreens: () => api.listScreens(),
  fetchFormFields: () => api.fetchFormFields(),
  runScreen: (id: number) => api.runScreen(id),
  deleteScreen: (id: number) => api.deleteScreen(id),
}));
const addToWatchlist = vi.fn();
vi.mock("../api/settings", () => ({
  fetchScreenColumnWidths: () => Promise.resolve({}),
  saveScreenColumnWidths: (widths: Record<string, number>) => Promise.resolve(widths),
}));
vi.mock("../api/watchlist", () => ({
  addToWatchlist: (ticker: string) => addToWatchlist(ticker),
  listWatchlist: () => Promise.resolve([]),
}));

describe("ScreensView", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("lists screens and shows results after running one", async () => {
    api.listScreens.mockResolvedValue([SCREEN]);
    api.fetchFormFields.mockResolvedValue({ options: {}, signals: {} });
    api.runScreen.mockResolvedValue({ rows: [], fetched_at: "2026-10-20T14:00:00Z" });
    render(<ScreensView onOpenStock={vi.fn()} />);

    expect(await screen.findByText("Top gainers — low float")).toBeInTheDocument();
    expect(screen.getByText(/feeds watchlist/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run Top gainers — low float" }));

    expect(await screen.findByText(/^No stocks match this screen right now\./)).toBeInTheDocument();
    expect(api.runScreen).toHaveBeenCalledWith(1);
  });

  it("shows the backend error when a run fails", async () => {
    api.listScreens.mockResolvedValue([SCREEN]);
    api.fetchFormFields.mockResolvedValue({ options: {}, signals: {} });
    api.runScreen.mockRejectedValue(new Error("Finviz is rate limiting requests (screen); try again in a minute."));
    render(<ScreensView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Run Top gainers — low float" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("rate limiting");
  });

  it("ignores a slow earlier run when another screen was clicked after it", async () => {
    const otherScreen: Screen = { ...SCREEN, id: 2, name: "After-hours" };
    api.listScreens.mockResolvedValue([SCREEN, otherScreen]);
    api.fetchFormFields.mockResolvedValue({ options: {}, signals: {} });
    let finishSlowRun: (run: unknown) => void = () => {};
    api.runScreen.mockImplementation((id: number) =>
      id === 1
        ? new Promise((resolve) => (finishSlowRun = resolve))
        : Promise.resolve({ rows: [], fetched_at: "2026-10-20T14:00:00Z" }),
    );
    render(<ScreensView onOpenStock={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Run Top gainers — low float" }));
    fireEvent.click(screen.getByRole("button", { name: "Run After-hours" }));
    await screen.findByRole("heading", { name: /After-hours/ });
    finishSlowRun({ rows: [], fetched_at: "2026-10-20T14:00:00Z" });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByRole("heading", { name: /After-hours/ })).toBeInTheDocument();
  });
});
