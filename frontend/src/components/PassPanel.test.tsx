import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DaySetup } from "../api/journal";
import { passEntry } from "../test/journalFixtures";
import { PassPanel } from "./PassPanel";

const api = vi.hoisted(() => ({ fetchReasons: vi.fn(), createEntry: vi.fn(), updateEntry: vi.fn() }));
vi.mock("../api/journal", () => ({
  fetchReasons: () => api.fetchReasons(),
  createEntry: (draft: unknown) => api.createEntry(draft),
  updateEntry: (id: number, draft: unknown) => api.updateEntry(id, draft),
}));

const CATALOG = {
  pass_reasons: [
    { group: "The app's read", items: [{ key: "low_sykes", label: "Low Sykes grade" }] },
    { group: "Me", items: [{ key: "other", label: "Other" }] },
  ],
  mistakes: [],
};
const SETUP: DaySetup = {
  setup_record_id: 7, pattern: "bull_flag", timeframe: "5m", direction: "long", entry: 2.12, stop: 2.05, target: 2.33,
  reward_risk: 3, score: 80, state: "forming", verdict: null, sliding_scale: null, outcome: "open",
};

describe("PassPanel", () => {
  beforeEach(() => {
    api.fetchReasons.mockResolvedValue(CATALOG);
    api.createEntry.mockResolvedValue({ id: 1, kind: "pass", bar_warning: null });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("can't be saved until a reason is picked", async () => {
    render(<PassPanel ticker="HOST" setups={[SETUP]} defaultSetupId={7} onSaved={vi.fn()} onClose={vi.fn()} />);

    const save = screen.getByRole("button", { name: "Save pass" });
    expect(save).toBeDisabled();
    fireEvent.click(await screen.findByRole("button", { name: "Low Sykes grade" }));

    expect(save).toBeEnabled();
  });

  it("needs a note when Other is picked", async () => {
    render(<PassPanel ticker="HOST" setups={[SETUP]} defaultSetupId={7} onSaved={vi.fn()} onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Other" }));
    expect(screen.getByRole("button", { name: "Save pass" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "spread too wide" } });

    expect(screen.getByRole("button", { name: "Save pass" })).toBeEnabled();
  });

  it("saves the picked reasons with the chosen setup", async () => {
    const onSaved = vi.fn();
    render(<PassPanel ticker="HOST" setups={[SETUP]} defaultSetupId={7} onSaved={onSaved} onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Low Sykes grade" }));
    fireEvent.click(screen.getByRole("button", { name: "Save pass" }));

    await vi.waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.createEntry).toHaveBeenCalledWith({
      kind: "pass", ticker: "HOST", direction: "long", setup_record_id: 7, reasons: ["low_sykes"], note: "",
      decided_at: null,
    });
  });

  it("shows why saving failed", async () => {
    api.createEntry.mockRejectedValue(new Error("Setup not found (id 7)."));
    render(<PassPanel ticker="HOST" setups={[SETUP]} defaultSetupId={7} onSaved={vi.fn()} onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Low Sykes grade" }));
    fireEvent.click(screen.getByRole("button", { name: "Save pass" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Setup not found (id 7).");
  });

  it("edits a saved pass in place, keeping when it was made", async () => {
    api.updateEntry.mockResolvedValue({ id: 4, kind: "pass", bar_warning: null });
    const existing = passEntry({ reasons: ["low_sykes"], note: "thin" });
    render(<PassPanel ticker="HOST" setups={[SETUP]} defaultSetupId={7} existing={existing} onSaved={vi.fn()} onClose={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Low Sykes grade" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Save pass" }));

    await vi.waitFor(() => expect(api.updateEntry).toHaveBeenCalled());
    expect(api.updateEntry).toHaveBeenCalledWith(4, expect.objectContaining({
      reasons: ["low_sykes"], note: "thin", decided_at: existing.decided_at,
    }));
  });
});
