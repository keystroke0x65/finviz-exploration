import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { QuoteTable } from "./QuoteTable";

describe("QuoteTable", () => {
  afterEach(() => {
    cleanup();
  });

  it("omits fields the backend sent as null", () => {
    render(
      <QuoteTable
        quote={{ Ticker: "AAPL", Company: "Apple Inc.", "P/E": null }}
        error={null}
        isLoading={false}
      />,
    );

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.queryByText("P/E")).not.toBeInTheDocument();
  });

  it("omits fields that are undefined", () => {
    render(
      <QuoteTable
        quote={{ Ticker: "AAPL", Company: undefined }}
        error={null}
        isLoading={false}
      />,
    );

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.queryByText("Company")).not.toBeInTheDocument();
  });

  it("renders the error message instead of a table when an error is set", () => {
    render(<QuoteTable quote={null} error="No Finviz data found" isLoading={false} />);

    expect(screen.getByRole("alert")).toHaveTextContent("No Finviz data found");
  });
});
