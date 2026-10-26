import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StockLink } from "./StockLink";

describe("StockLink", () => {
  afterEach(cleanup);

  it("links to the stock's own page so it can open in a new tab", () => {
    render(<StockLink ticker="HOST" onOpen={vi.fn()} />);

    expect(screen.getByRole("link", { name: "HOST" })).toHaveAttribute("href", "/?stock=HOST");
  });

  it("opens the stock in this tab on a plain click", () => {
    const onOpen = vi.fn();
    render(<StockLink ticker="HOST" onOpen={onOpen} />);

    const wasNotPrevented = fireEvent.click(screen.getByRole("link", { name: "HOST" }));

    expect(onOpen).toHaveBeenCalledWith("HOST");
    expect(wasNotPrevented).toBe(false);
  });

  it.each([
    ["Ctrl", { ctrlKey: true }],
    ["Cmd", { metaKey: true }],
    ["Shift", { shiftKey: true }],
    ["middle button", { button: 1 }],
  ])("leaves %s-clicks to the browser", (_name, modifiers) => {
    const onOpen = vi.fn();
    render(<StockLink ticker="HOST" onOpen={onOpen} />);

    const wasNotPrevented = fireEvent.click(screen.getByRole("link", { name: "HOST" }), modifiers);

    expect(onOpen).not.toHaveBeenCalled();
    expect(wasNotPrevented).toBe(true);
  });
});
