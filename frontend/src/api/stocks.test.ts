import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchQuote } from "./stocks";

describe("fetchQuote", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed quote data on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ Ticker: "AAPL", Price: "227.52" }),
      }),
    );

    const result = await fetchQuote("AAPL");

    expect(result).toEqual({ Ticker: "AAPL", Price: "227.52" });
    expect(fetch).toHaveBeenCalledWith("/api/stocks/AAPL");
  });

  it("throws with the backend's error detail on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "No Finviz data found for ticker 'ZZZZ'" }),
      }),
    );

    await expect(fetchQuote("ZZZZ")).rejects.toThrow(
      "No Finviz data found for ticker 'ZZZZ'",
    );
  });
});
