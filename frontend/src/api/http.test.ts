import { afterEach, describe, expect, it, vi } from "vitest";
import { requestJson } from "./http";

function stubFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

describe("requestJson", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the parsed body on success", async () => {
    stubFetch({ ok: true, status: 200, json: async () => ({ id: 1 }) });

    await expect(requestJson<{ id: number }>("/api/screens/1")).resolves.toEqual({ id: 1 });
  });

  it("throws the backend's detail message on failure", async () => {
    stubFetch({ ok: false, status: 503, json: async () => ({ detail: "Finviz is rate limiting" }) });

    await expect(requestJson("/api/screens/1/run")).rejects.toThrow("Finviz is rate limiting");
  });

  it("joins validation error messages when detail is a list", async () => {
    stubFetch({
      ok: false,
      status: 422,
      json: async () => ({ detail: [{ msg: "String should match pattern" }, { msg: "Field required" }] }),
    });

    await expect(requestJson("/api/screens")).rejects.toThrow(
      "String should match pattern; Field required",
    );
  });

  it("falls back to the status when the error body isn't JSON", async () => {
    stubFetch({
      ok: false,
      status: 500,
      json: async () => {
        throw new SyntaxError("Unexpected token '<'");
      },
    });

    await expect(requestJson("/api/screens")).rejects.toThrow("Request failed (500)");
  });

  it("returns undefined for 204 No Content without reading the body", async () => {
    const json = vi.fn();
    stubFetch({ ok: true, status: 204, json });

    await expect(requestJson("/api/screens/1", { method: "DELETE" })).resolves.toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});
