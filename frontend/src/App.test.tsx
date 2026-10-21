import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./components/ScreensView", () => ({ ScreensView: () => <p>screens view</p> }));
vi.mock("./components/WatchlistView", () => ({ WatchlistView: () => <p>watchlist view</p> }));

describe("App", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens on Screens and switches tabs", () => {
    render(<App />);
    expect(screen.getByText("screens view")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Watchlist" }));
    expect(screen.getByText("watchlist view")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Watchlist" })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("tab", { name: "Lookup" }));
    expect(screen.getByLabelText("Stock ticker")).toBeInTheDocument();
  });
});
