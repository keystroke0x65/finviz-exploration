import type { JournalEntry, StockFacts, TradeFigures } from "../api/journal";

export const NO_FACTS: StockFacts = {
  company: null, country: null, sector: null, industry: null, market_cap_millions: null, float_millions: null,
  price: null, change_percent: null, volume_so_far: null, volume_vs_average: null,
};

export const CLOSED_FIGURES: TradeFigures = {
  status: "closed", first_price: 1.84, average_entry: 1.84, average_exit: 2.05, shares_held: 0, max_shares: 500,
  money_in: 920, total_bought: 920, realised_pnl: 105, closed_pnl: [{ time: "2026-11-09T10:05:00-05:00", pnl: 105 }],
  fees: 0, net_pnl: 105, r_multiple: 2.63, planned_reward_risk: 3, opened_at: "2026-11-09T09:45:00-05:00",
  last_fill_at: "2026-11-09T10:05:00-05:00", duration_seconds: 1200,
};

export function tradeEntry(overrides: Partial<JournalEntry> = {}): JournalEntry {
  return {
    id: 3, kind: "trade", ticker: "HOST", direction: "long", created_at: "2026-11-09T10:10:00-05:00",
    updated_at: "2026-11-09T10:10:00-05:00", decided_at: "2026-11-09T09:45:00-05:00",
    setup: {
      setup_record_id: 7, pattern: "bull_flag", timeframe: "5m", direction: "long", entry: 1.84, stop: 1.76,
      target: 2.08, reward_risk: 3, score: 80, state: "forming", verdict: "leans_long",
      sliding_scale: { letter: "B", points: 10, factors: [] },
    },
    stock: { ...NO_FACTS, country: "USA", industry: "Software", price: 1.84 },
    plan_stop: 1.76, plan_target: 2.08, fees: 0, reasons: [], mistakes: ["chased"], note: "late entry", pass_price: null,
    fills: [
      { side: "buy", time: "2026-11-09T09:45:00-05:00", price: 1.84, shares: 500 },
      { side: "sell", time: "2026-11-09T10:05:00-05:00", price: 2.05, shares: 500 },
    ],
    figures: CLOSED_FIGURES, after_exit: { best_r: 1.4, worst_r: -0.5, best_price: 2.16, worst_price: 2.01 },
    plan_flags: ["exited_before_target"], pass_score: null, after_pass: null, bar_warning: null, ...overrides,
  };
}

export function passEntry(overrides: Partial<JournalEntry> = {}): JournalEntry {
  return tradeEntry({
    id: 4, kind: "pass", fills: [], figures: null, after_exit: null, plan_flags: [], mistakes: [], note: "",
    reasons: ["low_sykes", "too_late"], pass_price: 1.9, pass_score: { outcome: "stop", r: -1 }, ...overrides,
  });
}
