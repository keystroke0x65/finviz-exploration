import { useState } from "react";
import { LookupView } from "./components/LookupView";
import { ScreensView } from "./components/ScreensView";
import { WatchlistView } from "./components/WatchlistView";

const TABS = ["Screens", "Watchlist", "Lookup"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Screens");

  return (
    <div>
      <h1>Finviz Dashboard</h1>
      <nav role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>
      {activeTab === "Screens" && <ScreensView />}
      {activeTab === "Watchlist" && <WatchlistView />}
      {activeTab === "Lookup" && <LookupView />}
    </div>
  );
}
