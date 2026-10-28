# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Brainstorming a trading research system (movers journal -> measurements -> pattern search ->
live strategies, after how Dux/Sykes/Grattani/Kellogg work). Working notes:
docs/superpowers/specs/2026-10-27-trading-research-system-notes.md (not an approved design).
Dashboard: phases 1-2 + feedback batches merged and pushed (main = origin/main, 2026-10-26).
Docker runs from main on FRONTEND_PORT=5174 (now in .env). Backups in data/.

## Open questions / blockers
- Schwab developer API application not started (user's action).
- Deferred minors listed in progress.md (prog-0015).

## Recent changes
- 2026-10-27: "Scan this stock" now skips the 1m/5m bar cache and reloads chart + fresh
  quote; chart has a top-left OHLCV hover legend. Both merged to main and pushed (efda591).
- 2026-10-26: trigger time, chart volume/session shading, news time, stock links, scan
  status notice; snapshot JSON hotfix; '-' news time fix; main pushed.
- Track record (4 days, 3483 trades): generic setups lose (~-0.25R), mornings better,
  score/verdict don't separate winners; nearer targets don't fix it.

## Next steps
- Research the named traders' public scan criteria/setups, then continue the brainstorm.
