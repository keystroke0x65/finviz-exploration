# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 milestones 1, 2a and 2b merged into main (2b merge 0bdedea) on 2026-10-21; main not
pushed. Docker runs from main with FRONTEND_PORT=5174 on the real DB. Backups:
data/finviz_dashboard.db.backup-2026-10-21 (pre-2a), ...-2026-10-21-m2b (pre-2b).
Next: milestone 3 (continuation/reversal patterns, candlestick score modifiers, Track record
view, track record feeding ranking) — needs a plan.

## Open questions / blockers
- Schwab developer API application not started (user's action).
- FRONTEND_PORT=5174 not yet in user's .env.
- Deferred minors: 9 from M1, 8 remaining from M2a, 9 from M2b (verdict: single-input calls,
  location treats far support as bearish, no rel vol; micro pullback/ABCD crossing sessions;
  untyped dicts). Worth one cleanup batch before M3.

## Recent changes
- 2026-10-21: M2b built (9 tasks), reviewed (5 important fixed with tests), merged;
  live-verified at 12:28 ET (12 verdicts, new patterns firing, migration kept 195 setups).
- 2026-10-21: M2a merged earlier the same day.

## Next steps
- Ask user: deferred-minors cleanup batch vs milestone 3 plan.
