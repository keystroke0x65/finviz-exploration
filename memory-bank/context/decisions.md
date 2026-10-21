# Decisions — finviz-exploration

<!-- Entry file (ADR-style). One decision per root: "Chose X over Y because Z". When a decision
     changes, SUPERSEDE it — the old one moves to history/archive.md with the reason. -->

## Decisions
<!-- empty: architectural and product decisions with their rationale -->
- [dec-0003] root h=0 x=0 d=2026-10-21 labels=roadmap,phase2,patterns src="user-approved spec 2026-10-20" :: Phase 2 redefined (spec docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md): screens + auto watchlist (M1), bars + core/momentum patterns + per-stock verdict + outcome tracking (M2), continuation/reversal/candlestick + track record (M3). Everything direction-aware; short setups behind an off-by-default setting.

## Architecture
- [dec-0001] root h=1 x=0 d=2026-09-17 labels=security,architecture src="brainstorming session 2026-09-17" :: Backend owns all external API calls (Finviz, Schwab); frontend never calls them directly. Keeps the Finviz Elite token and Schwab credentials server-side only, never shipped to the browser.

## Finviz client design
- [dec-0002] root h=1 x=0 d=2026-09-17 labels=finviz,architecture src="brainstorming session 2026-09-17" :: A finviz_client module wraps Finviz's CSV export endpoints and cryptic filter codes behind typed Python functions (get_quote(ticker), run_screener(filters)); rest of app never touches raw CSV/URL-encoding or Finviz filter codes directly.
