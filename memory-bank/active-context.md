# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 milestones 1, 2a, 2b, a cleanup batch and M3 are merged into main (2026-10-21);
main not pushed. Docker runs from main with FRONTEND_PORT=5174 on the real DB. Backups in
data/: finviz_dashboard.db.backup-2026-10-21 (pre-2a), ...-m2b, ...-m3, backup-2026-10-26.

## Open questions / blockers
- Schwab developer API application not started (user's action).
- FRONTEND_PORT=5174 not yet in user's .env.
- Deferred minors listed in progress.md (prog-0015).

## Recent changes
- 2026-10-26: User feedback after a few days of trading: added trigger time on setups,
  volume + session shading on the chart, headline time on Screens (merged).
- 2026-10-21: M3 merged (track record, candles, 13 more pattern pairs); review fixed 4 issues
  (candle wick through stop, mid-range "breakouts", duplicate trades, avg win shown).
- 2026-10-21: Cleanup batch, M2b and M2a merged.

## Next steps
- Track record needs 5+ trading days before it moves scores; revisit numbers after a week.
- Options: cleanup batch for deferred minors, push main, or Phase 3 (needs Schwab).
