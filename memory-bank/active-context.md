# Active Context — finviz-exploration

<!-- Freeform, short-lived state. The agent MAY rewrite this file directly (the only exception
     to operations-only writes). Keep it under 80 lines. Durable facts belong in context/ or experience/. -->

## Current focus
Phase 1 design spec (foundation + stock lookup) is written and committed. Waiting on
user review before moving to the implementation plan. No code written yet.

## Open questions / blockers
- Schwab developer API application not yet started — needs to happen early since approval
  can take days (relevant once we reach phase 3, options). Asked user whether to start it
  now in parallel; awaiting answer.

## Recent changes
- Wrote and committed docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md.
- Repo initialized (git-skill); had to manually extend .gitignore for WSL Zone.Identifier
  and __pycache__ noise post-init (see experience/dev-environment.md trap).
- Memory bank initialized and seeded from the brainstorming session.

## Next steps
- Get user approval on the phase 1 spec (changes or go-ahead).
- On approval, invoke writing-plans for the phase 1 implementation plan.
- Resolve whether to start the Schwab developer API application now.
