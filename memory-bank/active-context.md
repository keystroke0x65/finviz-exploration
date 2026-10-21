# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 M1 merged into main (05d8327) on 2026-10-21; not yet pushed (main ahead of origin).
DB at data/finviz_dashboard.db (gitignored). Docker stack runs from main with
FRONTEND_PORT=5174 (user's other project holds 5173; FRONTEND_PORT not yet in .env).
Now: writing the M2 plan (bars, core+momentum patterns, trade plans, verdict, outcomes).

## Open questions / blockers
- Schwab developer API application not started (user's action; needed for phase 3).
- 9 deferred minor review findings from M1 (re-check codes on every save, expiry only
  inside feeder window, no screen name in history, order code unvalidated, etc.).

## Recent changes
- 2026-10-21: Removed old phase1/branch Docker containers, volume, images, network.
- 2026-10-21: Merged M1, copied DB into main data/, removed worktree + branch.
- 2026-10-20: Built M1 + UI redesign; spec deviation (save-time code validation).

## Next steps
- Write + execute M2 plan. Watchlist should gain today's price/change (wide-column batch).
