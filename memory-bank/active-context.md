# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 1 is merged into main (a9d414b) and pushed; feature worktree removed. Next up is
phase 2 (screener) — starts with a brainstorm -> spec -> plan cycle.

## Open questions / blockers
- Schwab developer API application not started (needed for phase 3; approval takes days).
  User has to do this themselves.
- origin/feat/phase1-foundation still exists on the remote (fully merged); delete if wanted.

## Recent changes
- 2026-10-20: Committed frontend lockfile, merged feat/phase1-foundation into main, tests
  green on merged result (17 pytest, 7 vitest, tsc clean). Copied .env from the worktree
  into the main checkout before removing it.
- 2026-10-20: Corrected stale memory bank (stack-0006, prog-0006..0008).

## Next steps
- Brainstorm phase 2 (screener).
- User: start Schwab developer API application.
