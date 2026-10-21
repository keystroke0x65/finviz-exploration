import { afterEach, describe, expect, it, vi } from "vitest";
import { createScreen, deleteScreen, parseScreenerUrl, runScreen } from "./screens";
import { addToWatchlist, removeFromWatchlist, setPinned } from "./watchlist";

function stubOkFetch(body: unknown = {}, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status, json: async () => body });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

describe("screens and watchlist API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("createScreen posts the input as JSON", async () => {
    const fetchMock = stubOkFetch({ id: 1 }, 201);
    const input = {
      name: "Mine",
      form: { country: "usa" as const, price_under: 20 },
      extra_filters: [],
      signal: null,
      order: null,
      feeds_watchlist: false,
    };

    await createScreen(input);

    expect(fetchMock).toHaveBeenCalledWith("/api/screens", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(input),
    });
  });

  it("runScreen posts to the screen's run endpoint", async () => {
    const fetchMock = stubOkFetch({ rows: [], is_possibly_unfiltered: false, fetched_at: "x" });

    await runScreen(3);

    expect(fetchMock).toHaveBeenCalledWith("/api/screens/3/run", { method: "POST" });
  });

  it("deleteScreen sends DELETE", async () => {
    const fetchMock = stubOkFetch(undefined, 204);

    await deleteScreen(4);

    expect(fetchMock).toHaveBeenCalledWith("/api/screens/4", { method: "DELETE" });
  });

  it("parseScreenerUrl posts the url", async () => {
    const fetchMock = stubOkFetch({ form: {}, extra_filters: [], signal: null, order: null });

    await parseScreenerUrl("https://finviz.com/screener.ashx?f=geo_usa");

    expect(fetchMock).toHaveBeenCalledWith("/api/screens/parse-url", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ url: "https://finviz.com/screener.ashx?f=geo_usa" }),
    });
  });

  it("addToWatchlist posts the ticker", async () => {
    const fetchMock = stubOkFetch({ ticker: "HOST" }, 201);

    await addToWatchlist("HOST");

    expect(fetchMock).toHaveBeenCalledWith("/api/watchlist", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ ticker: "HOST" }),
    });
  });

  it("encodes tickers in watchlist paths", async () => {
    const fetchMock = stubOkFetch(undefined, 204);

    await removeFromWatchlist("BRK.B");
    await setPinned("BRK.B", true);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/watchlist/BRK.B", { method: "DELETE" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/watchlist/BRK.B", {
      method: "PATCH",
      headers: JSON_HEADERS,
      body: JSON.stringify({ is_pinned: true }),
    });
  });
});
