# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 milestone 1 (screens + watchlist feeder) is built and reviewed on branch
feat/phase2-m1-screens-watchlist (worktree .worktrees/feat-phase2-m1). Awaiting the
user's choice: merge locally / PR / keep. Local smoke servers may still be running
(uvicorn :8000 with scratch DB, vite :5174).

## Open questions / blockers
- Schwab developer API application not started (user's action; needed for phase 3).
- Docker not reachable from WSL right now (Docker Desktop integration) — Docker run of
  M1 not verified; local uvicorn+vite smoke test passed against live Finviz.
- 9 deferred minor review findings (see M1 final report in conversation; e.g. re-checking
  codes on every save, expiry only inside feeder window, no screen name in history).

## Recent changes
- 2026-10-20: Built M1 (10 plan tasks + 3 review fixes). Spec deviation: replaced
  ">5,000 rows = ignored filters" with save-time code validation after a live check.
- 2026-10-20: Phase 2 spec + M1 plan committed on main.

## Next steps
- Integrate the M1 branch, then write the M2 plan.
