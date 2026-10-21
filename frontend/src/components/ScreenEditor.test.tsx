import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FormFields } from "../api/screens";
import { ScreenEditor } from "./ScreenEditor";

const parseScreenerUrl = vi.fn();
vi.mock("../api/screens", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/screens")>()),
  parseScreenerUrl: (url: string) => parseScreenerUrl(url),
}));

const FORM_FIELDS: FormFields = {
  options: {
    country: ["usa"],
    price_under: [5, 10, 20],
    float_under_millions: [10, 20],
    market_cap: ["large_and_under", "nano"],
    volume_over_thousands: [1000],
    relative_volume_over: [1.5, 2],
  },
  signals: { ta_topgainers: "Top gainers" },
};

function renderEditor(onSave = vi.fn().mockResolvedValue(undefined)) {
  render(<ScreenEditor initial={null} formFields={FORM_FIELDS} onSave={onSave} onCancel={vi.fn()} />);
  return onSave;
}

describe("ScreenEditor", () => {
  afterEach(() => {
    cleanup();
    parseScreenerUrl.mockReset();
  });

  it("fills the form from a pasted Finviz URL", async () => {
    parseScreenerUrl.mockResolvedValue({
      form: { country: "usa", price_under: 20, float_under_millions: null, market_cap: null,
        volume_over_thousands: null, relative_volume_over: null },
      extra_filters: ["ta_rsi_os30"],
      signal: "ta_topgainers",
      order: "-change",
    });
    renderEditor();

    fireEvent.change(screen.getByLabelText("Finviz screener URL"), {
      target: { value: "https://finviz.com/screener.ashx?f=geo_usa,sh_price_u20,ta_rsi_os30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(screen.getByLabelText("Price under ($)")).toHaveValue("20"));
    expect(screen.getByLabelText("Country")).toHaveValue("usa");
    expect(screen.getByLabelText("Signal")).toHaveValue("ta_topgainers");
    expect(screen.getByText("ta_rsi_os30")).toBeInTheDocument();
  });

  it("shows the backend error when a pasted URL is rejected", async () => {
    parseScreenerUrl.mockRejectedValue(new Error("Paste a screener URL from finviz.com"));
    renderEditor();

    fireEvent.change(screen.getByLabelText("Finviz screener URL"), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Paste a screener URL from finviz.com");
  });

  it("saves the form as a screen input with numbers and removed chips", async () => {
    parseScreenerUrl.mockResolvedValue({
      form: {}, extra_filters: ["ta_rsi_os30", "fa_pe_u10"], signal: null, order: "-change",
    });
    const onSave = renderEditor();
    fireEvent.change(screen.getByLabelText("Finviz screener URL"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await screen.findByText("fa_pe_u10");

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Low float" } });
    fireEvent.change(screen.getByLabelText("Relative volume over"), { target: { value: "1.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Remove ta_rsi_os30" }));
    fireEvent.click(screen.getByLabelText("Feeds watchlist"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith({
      name: "Low float",
      form: { country: null, price_under: null, float_under_millions: null, market_cap: null,
        volume_over_thousands: null, relative_volume_over: 1.5 },
      extra_filters: ["fa_pe_u10"],
      signal: null,
      order: "-change",
      feeds_watchlist: true,
    });
  });

  it("shows backend error detail when save fails", async () => {
    renderEditor(vi.fn().mockRejectedValue(new Error("price_under=17 is not one of [5, 10, 20]")));

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Mine" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("price_under=17 is not one of");
  });
});
