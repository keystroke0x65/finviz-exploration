# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 2 M2a (bars, patterns, trade plans, ranking, outcomes, scans, Setups + Stock views)
is BUILT on branch feat/phase2-m2a-setups (worktree .worktrees/feat-phase2-m2a), 15 commits,
251 backend + 84 frontend tests green, live-verified against Finviz. NOT merged.
Remaining: whole-branch review (reviewer was stopped at usage limit — rerun it with
review-package + code-reviewer prompt), fix Critical/Important, then merge to main.

## Running state
- Docker stack currently runs FROM THE WORKTREE on :5174 with a COPY of the DB
  (.worktrees/feat-phase2-m2a/data/). Main-folder stack is stopped; main's data/ DB untouched.
  After merge: stop worktree stack, run from main (FRONTEND_PORT=5174).

## Open questions / blockers
- Schwab developer API application not started (user's action).
- Deferred minors from M1 still open; uvicorn --reload re-runs feeder+scan on every reload.
- Ledger with all rulings: .worktrees/feat-phase2-m2a/.superpowers/sdd/2026-10-21-phase2-m2a-setups-engine/progress.md

## Next steps
- Final review of M2a, merge, then plan M2b (triangles, doubles, ABCD, micro/first pullback, verdict).
