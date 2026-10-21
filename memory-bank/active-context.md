# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 M2a merged into main (041ea54) on 2026-10-21; main not pushed (41 commits ahead).
Docker runs from main with FRONTEND_PORT=5174 on the real DB (data/finviz_dashboard.db);
backup before M2a schema: data/finviz_dashboard.db.backup-2026-10-21.
Next: write the M2b plan (triangles, double top/bottom, ABCD, micro pullback, first
pullback, EMAs, per-stock verdict), then M3 (continuation/reversal/candlesticks + track record).

## Open questions / blockers
- Schwab developer API application not started (user's action).
- FRONTEND_PORT=5174 not yet in user's .env.
- Deferred minors: 9 from M1 review, 9 from M2a review (trailing stop bounds, direction-aware
  conflict badge, stale daily state, concurrent-scan lock, sort bars, StockView stale
  responses, auth path skipped list, ranking counts plan-less matches, API returns short
  plans in warnings).

## Recent changes
- 2026-10-21: M2a built (14 tasks), reviewed (1 critical + 5 important fixed with tests),
  merged; live-verified pre-market against Finviz.
- 2026-10-21: Removed old phase1/branch Docker containers, volumes, images.

## Next steps
- M2b plan when the user is ready; consider fixing the deferred minors in a small batch.
