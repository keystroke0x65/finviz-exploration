import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { NewsList } from "./NewsList";

const NOW = new Date("2026-11-11T17:00:00Z");
const DAY_MS = 86_400_000;

function itemDaysAgo(days: number, title: string) {
  return { time: new Date(NOW.getTime() - days * DAY_MS).toISOString(), source: "GlobeNewswire", title, url: `https://example.com/${days}` };
}

const ITEMS = [itemDaysAgo(1, "Fresh deal"), itemDaysAgo(20, "Older update"), itemDaysAgo(60, "Ancient news")];

describe("NewsList", () => {
  afterEach(cleanup);

  it("starts with the last 2 weeks and links each title to its article", () => {
    render(<NewsList items={ITEMS} error={null} now={NOW} />);

    const link = screen.getByRole("link", { name: "Fresh deal" });
    expect(link).toHaveAttribute("href", "https://example.com/1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.getByText("GlobeNewswire")).toBeInTheDocument();
    expect(screen.queryByText("Older update")).not.toBeInTheDocument();
  });

  it("adds older news 2 weeks at a time, skipping empty stretches", () => {
    render(<NewsList items={ITEMS} error={null} now={NOW} />);

    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByText("Older update")).toBeInTheDocument();
    expect(screen.queryByText("Ancient news")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByText("Ancient news")).toBeInTheDocument();
    expect(screen.getByText("No news Sep 16 – Oct 14")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("says so when the last 2 weeks had no news, and still offers older news", () => {
    render(<NewsList items={[itemDaysAgo(30, "Quiet month")]} error={null} now={NOW} />);

    expect(screen.getByText("No news in the last 2 weeks.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByText("Quiet month")).toBeInTheDocument();
  });

  it("shows loading and errors", () => {
    const { rerender } = render(<NewsList items={null} error={null} now={NOW} />);
    expect(screen.getByText("Loading news…")).toBeInTheDocument();

    rerender(<NewsList items={null} error="Finviz is rate limiting requests" now={NOW} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load news: Finviz is rate limiting requests");
  });

  it("keeps the news in a scrolling box with Show more inside it", () => {
    render(<NewsList items={ITEMS} error={null} now={NOW} />);

    const box = screen.getByRole("region", { name: "News articles" });
    expect(box).toHaveClass("news-scroll");
    expect(box).toContainElement(screen.getByRole("link", { name: "Fresh deal" }));
    expect(box).toContainElement(screen.getByRole("button", { name: "Show more" }));
  });

  it("sizes the box to its first 5 articles", () => {
    const many = Array.from({ length: 8 }, (_, index) => itemDaysAgo(index * 0.1, `Story ${index}`));
    render(<NewsList items={many} error={null} now={NOW} />);
    const box = screen.getByRole("region", { name: "News articles" });
    const rows = box.querySelectorAll(".news-row");
    rows.forEach((row, index) => {
      Object.defineProperty(row, "offsetTop", { value: index * 40, configurable: true });
      Object.defineProperty(row, "offsetHeight", { value: 40, configurable: true });
    });

    fireEvent(window, new Event("resize"));

    expect(box.style.maxHeight).toBe("200px");
  });
});
