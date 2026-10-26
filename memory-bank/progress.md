# Progress — finviz-exploration

<!-- Entry file. Changed only through memory.py apply. Move items between sections with UPDATE + section. -->

## Now
<!-- empty: work in progress -->

## Next
<!-- empty: planned work, highest priority first -->

## Done
<!-- empty: completed milestones (keep the latest 15; consolidate archives older ones) -->
- [prog-0001] root h=0 x=0 d=2026-09-17 labels=status src="user" :: Brainstorming/design phase complete for Phase 1 (foundation + stock lookup). Writing design spec doc next, then an implementation plan.
- [prog-0007] root h=0 x=0 d=2026-10-20 labels=status,phase1 src="git log main" supersedes=prog-0004 :: Phase 1 (foundation + stock lookup) merged into main on 2026-10-20 (merge a9d414b) and pushed; 17 backend pytest + 7 frontend vitest tests green on merged result. Feature worktree removed.
- [prog-0017] root h=0 x=0 d=2026-10-26 labels=status,phase2 src="git log main" supersedes=prog-0016 :: Phase 2 M1-M3 + cleanup + 2026-10-26 feedback batch merged; then hotfix d1c9f9d (scans crashed on snapshot JSON) and stock links b8fec96 (tickers are /?stock=TICKER links, new-tab capable). 425 backend + 136 frontend tests; main not pushed.

## Known issues
<!-- empty: bugs, tech debt, limitations still open -->
- [prog-0006] root h=0 x=0 d=2026-10-20 labels=schwab,options src="user" :: Schwab developer API application still not started; approval can take days and phase 3 (options chain) depends on it. Ask user whether to start it in parallel now.
- [prog-0015] root h=0 x=0 d=2026-10-21 labels=phase2,tech-debt src="M3 final review" :: Deferred minors: cleanup batch (daily state uses thin pre-market prints, single-ticker scan 409s during scheduled scan, volume reason ignores rel-vol scaling); M3 (V-shaped cups/rounding accepted, H&S lacks prior trend/min height, history lookup full-scans, candle tolerance vs tight risk, ranking imports setups).
