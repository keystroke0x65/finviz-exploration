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

  it("throws a status-based message when the error response isn't valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new SyntaxError("Unexpected token '<', \"<html>\" is not valid JSON");
        },
      }),
    );

    await expect(fetchQuote("AAPL")).rejects.toThrow("Request failed (500)");
  });

  it("does not read the response body before checking ok on success", async () => {
    let bodyReadCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => {
          bodyReadCount += 1;
          return { Ticker: "AAPL", Price: "227.52" };
        },
      }),
    );

    const result = await fetchQuote("AAPL");

    expect(result).toEqual({ Ticker: "AAPL", Price: "227.52" });
    expect(bodyReadCount).toBe(1);
  });
});
