# Decisions — finviz-exploration

<!-- Entry file (ADR-style). One decision per root: "Chose X over Y because Z". When a decision
     changes, SUPERSEDE it — the old one moves to history/archive.md with the reason. -->

## Decisions
<!-- empty: architectural and product decisions with their rationale -->

## Architecture
- [dec-0001] root h=0 x=0 d=2026-09-17 labels=security,architecture src="brainstorming session 2026-09-17" :: Backend owns all external API calls (Finviz, Schwab); frontend never calls them directly. Keeps the Finviz Elite token and Schwab credentials server-side only, never shipped to the browser.

## Finviz client design
- [dec-0002] root h=0 x=0 d=2026-09-17 labels=finviz,architecture src="brainstorming session 2026-09-17" :: A finviz_client module wraps Finviz's CSV export endpoints and cryptic filter codes behind typed Python functions (get_quote(ticker), run_screener(filters)); rest of app never touches raw CSV/URL-encoding or Finviz filter codes directly.
