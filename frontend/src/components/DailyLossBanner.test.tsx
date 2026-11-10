import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DailyLossBanner } from "./DailyLossBanner";

const api = vi.hoisted(() => ({ fetchDailyLoss: vi.fn() }));
vi.mock("../api/journal", () => ({ fetchDailyLoss: () => api.fetchDailyLoss() }));

describe("DailyLossBanner", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows nothing while under the limit", async () => {
    api.fetchDailyLoss.mockResolvedValue({ realised_pnl_today: -20, max_daily_loss: 200, level: "ok" });

    const { container } = render(<DailyLossBanner refreshKey={0} />);

    await vi.waitFor(() => expect(api.fetchDailyLoss).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("warns when close to the limit", async () => {
    api.fetchDailyLoss.mockResolvedValue({ realised_pnl_today: -170, max_daily_loss: 200, level: "warning" });

    render(<DailyLossBanner refreshKey={0} />);

    expect(await screen.findByRole("status")).toHaveTextContent("Close to max daily loss (−$170 of −$200)");
  });

  it("alerts when the limit is reached", async () => {
    api.fetchDailyLoss.mockResolvedValue({ realised_pnl_today: -212, max_daily_loss: 200, level: "reached" });

    render(<DailyLossBanner refreshKey={0} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Max daily loss reached (−$212 of −$200)");
  });
});
