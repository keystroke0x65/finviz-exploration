import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDaySetups } from "./useDaySetups";

const api = vi.hoisted(() => ({ fetchDaySetups: vi.fn() }));
vi.mock("./api/journal", () => ({ fetchDaySetups: (...args: unknown[]) => api.fetchDaySetups(...args) }));

const EMPTY = { matches: [], others: [] };

describe("useDaySetups", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("asks for the setups around the trade's first fill", async () => {
    vi.useFakeTimers();
    api.fetchDaySetups.mockResolvedValue(EMPTY);

    renderHook(() => useDaySetups("HOST", { time: "2026-11-16T09:45:00-05:00", price: 0.76 }, "long"));
    await act(() => vi.advanceTimersByTimeAsync(400));

    expect(api.fetchDaySetups).toHaveBeenCalledWith("HOST", "2026-11-16", "2026-11-16T09:45:00-05:00", "long", 0.76);
  });

  it("waits for typing to settle before asking again", async () => {
    vi.useFakeTimers();
    api.fetchDaySetups.mockResolvedValue(EMPTY);
    const { rerender } = renderHook(({ price }) => useDaySetups("HOST", { time: "2026-11-16T09:45:00-05:00", price }, "long"), {
      initialProps: { price: 0.7 },
    });

    rerender({ price: 0.75 });
    rerender({ price: 0.76 });
    await act(() => vi.advanceTimersByTimeAsync(400));

    expect(api.fetchDaySetups).toHaveBeenCalledTimes(1);
    expect(api.fetchDaySetups.mock.calls[0][4]).toBe(0.76);
  });

  it("without a fill, asks for the setups live now in any direction", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-16T15:00:00Z"));
    api.fetchDaySetups.mockResolvedValue(EMPTY);

    const { result } = renderHook(() => useDaySetups("HOST", null, null));
    await act(() => vi.advanceTimersByTimeAsync(400));

    expect(api.fetchDaySetups).toHaveBeenCalledWith("HOST", "2026-11-16", "2026-11-16T15:00:00.400Z", undefined, undefined);
    expect(result.current).toEqual({ setups: EMPTY, error: null });
  });
});
