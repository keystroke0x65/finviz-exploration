import { useState } from "react";
import { LookupView } from "./components/LookupView";
import { ScreensView } from "./components/ScreensView";
import { SessionStrip } from "./components/SessionStrip";
import { WatchlistView } from "./components/WatchlistView";

const TABS = ["Screens", "Watchlist", "Lookup"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Screens");

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
        {activeTab === "Screens" && <ScreensView />}
        {activeTab === "Watchlist" && <WatchlistView />}
        {activeTab === "Lookup" && <LookupView />}
      </main>
    </>
  );
}
