import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./components/ScreensView", () => ({ ScreensView: () => <p>screens view</p> }));
vi.mock("./components/SetupsView", () => ({
  SetupsView: ({ onOpenStock }: { onOpenStock: (ticker: string) => void }) => (
    <button type="button" onClick={() => onOpenStock("HOST")}>open HOST</button>
  ),
}));
vi.mock("./components/StockView", () => ({ StockView: ({ ticker }: { ticker: string | null }) => <p>stock view {ticker ?? "none"}</p> }));
vi.mock("./components/WatchlistView", () => ({ WatchlistView: () => <p>watchlist view</p> }));

describe("App", () => {
  afterEach(() => {
    cleanup();
    window.history.replaceState(null, "", "/");
  });

  it("opens on Setups and switches tabs", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: "open HOST" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Screens" }));
    expect(screen.getByText("screens view")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Watchlist" }));
    expect(screen.getByText("watchlist view")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Watchlist" })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("tab", { name: "Stock" }));
    expect(screen.getByText("stock view none")).toBeInTheDocument();
  });

  it("opens the stock tab for a ticker picked elsewhere", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "open HOST" }));

    expect(screen.getByRole("tab", { name: "Stock" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("stock view HOST")).toBeInTheDocument();
  });

  it("opens straight onto a stock named in the address", () => {
    window.history.replaceState(null, "", "/?stock=host");

    render(<App />);

    expect(screen.getByRole("tab", { name: "Stock" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("stock view HOST")).toBeInTheDocument();
  });

  it("ignores a malformed ticker in the address", () => {
    window.history.replaceState(null, "", "/?stock=%3Cscript%3E");

    render(<App />);

    expect(screen.getByRole("tab", { name: "Setups" })).toHaveAttribute("aria-selected", "true");
  });

  it("keeps the address on the stock being viewed, and clears it on other tabs", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "open HOST" }));
    expect(window.location.search).toBe("?stock=HOST");

    fireEvent.click(screen.getByRole("tab", { name: "Screens" }));
    expect(window.location.search).toBe("");
  });
});
