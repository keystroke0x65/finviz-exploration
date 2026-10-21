# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 milestones 1, 2a, 2b and a cleanup batch are merged into main (2026-10-21); main not
pushed. Docker runs from main with FRONTEND_PORT=5174 on the real DB. Backups in data/:
finviz_dashboard.db.backup-2026-10-21 (pre-2a), ...-m2b (pre-2b).
Next: milestone 3 plan (continuation/reversal patterns, candlestick score modifiers, Track
record view, track record feeding ranking).

## Open questions / blockers
- Schwab developer API application not started (user's action).
- FRONTEND_PORT=5174 not yet in user's .env.
- 4 deferred minors (see progress.md).

## Recent changes
- 2026-10-21: Cleanup batch (7 tasks, ~22 minors + 5 review fixes) merged; live check OK.
- 2026-10-21: M2b merged (patterns + verdict); M2a merged (setups engine).

## Next steps
- Milestone 3 plan when the user is ready.
