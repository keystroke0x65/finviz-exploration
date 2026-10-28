# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Brainstorming a trading research system modelled on how Dux/Sykes/Grittani/Kellogg work.
All decisions and the hand-off steps are in
docs/superpowers/specs/2026-10-27-trading-research-system-notes.md (read it first; see its
"How to continue" section). Not an approved design yet.
Decided (2026-10-27): system-created tables seeded from those traders' setups, long-biased
tables too; user approves new tables/patterns before live alerts; worthwhile = average profit
per trade after costs (win rate shown); first part to build = movers journal; build order
journal -> table stats -> live A-F grades -> lookalike search -> pattern lifecycle -> approvals.
Dashboard: phases 1-2 + feedback batches merged and pushed. Docker runs from main on
FRONTEND_PORT=5174 (in .env). Backups in data/.

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
- Continue the brainstorm on the movers journal only: review its columns with the user, decide
  which stocks enter, then write the journal design doc and get approval.
