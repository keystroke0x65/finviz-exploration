import { useState } from "react";
import { LookupView } from "./components/LookupView";
import { ScreensView } from "./components/ScreensView";
import { SetupsView } from "./components/SetupsView";
import { SessionStrip } from "./components/SessionStrip";
import { WatchlistView } from "./components/WatchlistView";

const TABS = ["Setups", "Screens", "Watchlist", "Lookup"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Setups");

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
        {activeTab === "Setups" && <SetupsView onOpenStock={() => setActiveTab("Lookup")} />}
        {activeTab === "Screens" && <ScreensView />}
        {activeTab === "Watchlist" && <WatchlistView />}
        {activeTab === "Lookup" && <LookupView />}
      </main>
    </>
  );
}
