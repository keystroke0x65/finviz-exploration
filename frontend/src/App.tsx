import { useEffect, useState } from "react";
import { ScreensView } from "./components/ScreensView";
import { SessionStrip } from "./components/SessionStrip";
import { SetupsView } from "./components/SetupsView";
import { StockView } from "./components/StockView";
import { TrackRecordView } from "./components/TrackRecordView";
import { WatchlistView } from "./components/WatchlistView";
import { readTickerFromSearch, stockUrl } from "./stockLink";

const TABS = ["Setups", "Screens", "Watchlist", "Stock", "Track record"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  // A link like /?stock=HOST (e.g. opened in a new tab) starts on that stock.
  const [stockTicker, setStockTicker] = useState<string | null>(() => readTickerFromSearch(window.location.search));
  const [activeTab, setActiveTab] = useState<Tab>(() => (stockTicker ? "Stock" : "Setups"));

  // Keep the address on the stock being viewed so a refresh or a copied link returns to
  // it. replaceState, not pushState: tabs aren't pages, so Back shouldn't step through them.
  useEffect(() => {
    const address = activeTab === "Stock" && stockTicker ? stockUrl(stockTicker) : "/";
    if (address !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(null, "", address);
    }
  }, [activeTab, stockTicker]);

  function openStock(ticker: string) {
    setStockTicker(ticker);
    setActiveTab("Stock");
  }

  return (
    <>
      <header className="app-header">
        <h1 className="app-title">Finviz Dashboard</h1>
        <SessionStrip />
        <nav className="tabs" role="tablist" aria-label="Sections">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              className="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">
        {activeTab === "Setups" && <SetupsView onOpenStock={openStock} />}
        {activeTab === "Screens" && <ScreensView onOpenStock={openStock} />}
        {activeTab === "Watchlist" && <WatchlistView onOpenStock={openStock} />}
        {activeTab === "Stock" && <StockView ticker={stockTicker} onTickerChange={setStockTicker} />}
        {activeTab === "Track record" && <TrackRecordView />}
      </main>
    </>
  );
}
