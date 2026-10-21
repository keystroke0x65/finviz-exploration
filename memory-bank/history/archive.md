# Archive

Superseded, deleted and promoted entries. Not loaded by default.

- 2026-10-20 SUPERSEDE batch=b-20261020-232507-u9m5 file=context/tech-stack.md reason="verified endpoint in backend/app/finviz_client.py on feat/phase1-foundation"
  - [stack-0004] root h=0 x=1 d=2026-09-17 labels=finviz,api src="user" :: Finviz Elite export API (CSV endpoints at export.finviz.com, auth via static token in URL) for quotes/screener/fundamentals. Finviz has NO options data at all (no chains, IV, or greeks) on any tier.
- 2026-10-20 SUPERSEDE batch=b-20261020-232507-u9m5 file=progress.md reason="phase 1 spec approved and implemented since"
  - [prog-0003] root h=0 x=1 d=2026-09-17 labels=status src="user" :: Awaiting user review of phase 1 spec (docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md) and a decision on whether to start the Schwab developer API application now (approval takes days) even though it's not needed until phase 3.
- 2026-10-20 SUPERSEDE batch=b-20261020-232507-u9m5 file=progress.md reason="plan written and executed; next step changed"
  - [prog-0002] root h=0 x=0 d=2026-09-17 labels=roadmap src="brainstorming session 2026-09-17" :: After phase 1 spec is approved: invoke writing-plans skill for the phase 1 implementation plan. Later phases (screener, options/Schwab, watchlists, etc.) each get their own brainstorm -> spec -> plan cycle.
- 2026-10-20 SUPERSEDE batch=b-20261020-233106-73id file=progress.md reason="merged to main 2026-10-20"
  - [prog-0004] root h=1 x=0 d=2026-10-20 labels=status,git src="git log main..feat/phase1-foundation" supersedes=prog-0003 :: Phase 1 (foundation + stock lookup) implemented on branch feat/phase1-foundation (worktree .worktrees/feat-phase1-foundation, pushed to origin) but NOT merged to main and no PR yet; frontend/package-lock.json untracked there. Verified end-to-end with real token on 2026-09-18.
- 2026-10-20 SUPERSEDE batch=b-20261020-233106-73id file=progress.md reason="merge done; next step is phase 2"
  - [prog-0005] root h=1 x=0 d=2026-10-20 labels=roadmap src="user roadmap" supersedes=prog-0002 :: Next: merge feat/phase1-foundation into main (commit lockfile, run pytest + vitest first), then start phase 2 (screener) with its own brainstorm -> spec -> plan cycle.
- 2026-10-21 SUPERSEDE batch=b-20261021-024002-sfvh file=progress.md reason="phase 2 spec approved and M1 plan written"
  - [prog-0008] root h=1 x=0 d=2026-10-20 labels=roadmap,screener src="docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md" supersedes=prog-0005 :: Next: phase 2 (screener: Finviz screener export, filter UI, saved queries) via its own brainstorm -> spec -> plan cycle.
- 2026-10-21 SUPERSEDE batch=b-20261021-032258-luyc file=experience/finviz.md reason="live check showed codes are ignored one by one, not whole screen"
  - [finviz-0001] trap h=0 x=1 d=2026-10-21 labels=finviz,screener,filters src="probe of elite.finviz.com/export 2026-10-20" :: FAILED: assuming Finviz rejects bad filter codes -> unknown f=/s= codes are silently ignored and the export returns the whole market (~10,400 rows). INSTEAD: treat >5,000 rows as 'filters may have been ignored' and verify every code via the sanity script.
- 2026-10-21 SUPERSEDE batch=b-20261021-032258-luyc file=progress.md reason="M1 implemented and reviewed"
  - [prog-0009] root h=0 x=0 d=2026-10-21 labels=roadmap,phase2 src="docs/superpowers/plans/2026-10-20-phase2-m1-screens-watchlist.md" supersedes=prog-0008 :: Next: execute docs/superpowers/plans/2026-10-20-phase2-m1-screens-watchlist.md (10 tasks: screens + watchlist feeder) once user picks execution approach; then plan M2.
- 2026-10-21 SUPERSEDE batch=b-20261021-160602-orrg file=progress.md reason="M1 and M2a both merged to main"
  - [prog-0010] root h=1 x=0 d=2026-10-21 labels=status,phase2 src="git log main..feat/phase2-m1-screens-watchlist" supersedes=prog-0009 :: Phase 2 M1 (screens + watchlist feeder) built on branch feat/phase2-m1-screens-watchlist (worktree .worktrees/feat-phase2-m1), 15 commits, 134 backend + 39 frontend tests, final review fixes applied; awaiting user's merge/PR choice. Next: plan M2 (bars, core+momentum patterns, verdict, outcome tracking).
