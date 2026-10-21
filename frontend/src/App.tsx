import { useState } from "react";
import { ScreensView } from "./components/ScreensView";
import { SessionStrip } from "./components/SessionStrip";
import { SetupsView } from "./components/SetupsView";
import { StockView } from "./components/StockView";
import { WatchlistView } from "./components/WatchlistView";

const TABS = ["Setups", "Screens", "Watchlist", "Stock"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Setups");
  const [stockTicker, setStockTicker] = useState<string | null>(null);

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
      </main>
    </>
  );
}
