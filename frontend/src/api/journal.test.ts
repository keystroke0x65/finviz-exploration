import { afterEach, describe, expect, it, vi } from "vitest";
import { createEntry, deleteEntry, exportUrl, fetchDaySetups, fetchEntries, fetchSummary, previewTrade } from "./journal";
import type { TradeDraft } from "./journal";

const TRADE: TradeDraft = {
  kind: "trade",
  ticker: "HOST",
  direction: "long",
  setup_record_id: 7,
  plan_stop: 1.9,
  plan_target: 2.3,
  fees: 0,
  mistakes: [],
  note: "",
  fills: [{ side: "buy", time: "2026-11-09T09:45:00-05:00", price: 2, shares: 100 }],
};

function stubFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("journal api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts a new entry as JSON", async () => {
    const fetchMock = stubFetch({ id: 1 });

    await createEntry(TRADE);

    expect(fetchMock).toHaveBeenCalledWith("/api/journal/entries", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(TRADE);
  });

  it("previews a trade", async () => {
    const fetchMock = stubFetch({ figures: null, error: "Add at least one fill." });

    expect(await previewTrade(TRADE)).toEqual({ figures: null, error: "Add at least one fill." });
    expect(fetchMock).toHaveBeenCalledWith("/api/journal/preview", expect.objectContaining({ method: "POST" }));
  });

  it("lists entries for a kind and period", async () => {
    const fetchMock = stubFetch([]);

    await fetchEntries("trade", "week");

    expect(fetchMock).toHaveBeenCalledWith("/api/journal/entries?period=week&kind=trade");
  });

  it("asks for a summary of a period", async () => {
    const fetchMock = stubFetch({});

    await fetchSummary("month");

    expect(fetchMock).toHaveBeenCalledWith("/api/journal/summary?period=month");
  });

  it("encodes the moment when asking for a day's setups", async () => {
    const fetchMock = stubFetch([]);

    await fetchDaySetups("HOST", "2026-11-09", "2026-11-09T09:45:00-05:00");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/journal/setups/HOST?day=2026-11-09&at=2026-11-09T09%3A45%3A00-05%3A00",
    );
  });

  it("deletes an entry", async () => {
    const fetchMock = stubFetch(undefined, 204);

    await deleteEntry(3);

    expect(fetchMock).toHaveBeenCalledWith("/api/journal/entries/3", { method: "DELETE" });
  });

  it("builds export links", () => {
    expect(exportUrl("fills", "all")).toBe("/api/journal/export/fills.csv?period=all");
  });
});
