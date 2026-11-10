# 0005: Save journal bars per stock-day in their own table
Date: 2026-11-09
Status: accepted

## Context
The trade journal must redraw a trade's 1-minute chart weeks later, but Finviz only
returns about two weeks of 1-minute bars. The existing `bar_cache` table keeps one row per
(ticker, interval) and is overwritten on every fetch, so it can't hold history. The
research-record draft (2026-11-06) also plans to store minute bars, but it isn't approved
or built.

## Decision
A `journal_bar_days` table stores the 4:00 AM-8:00 PM ET 1-minute bars once per
(ticker, trading day) as JSON, with a status: `partial` (saved before 8 PM), `complete`, or
`missing` (Finviz no longer has the day). Every journal entry on that stock-day shares the
row. Bars are saved when an entry is logged; the existing background loop completes
partial days and retries failed fetches. 5-minute bars are built from the 1-minute ones
when shown.

## Alternatives considered
- **Save a screenshot of the chart:** frozen at one zoom, needs a headless browser in
  Docker, and loses the hover legend and timeframe switch.
- **Extend `bar_cache` to keep history:** mixes a short-lived cache with permanent data
  the user can't lose; cache clean-ups would risk journal charts.
- **Wait for the research record's minute-bar store:** not built; the journal would have
  no charts until it is.

## Consequences
- Charts survive Finviz's two-week window, and each stock-day costs one request.
- About 1,000 bars (~60 KB of JSON) per stock-day; fine for a personal journal.
- If the research record later stores the same bars, the two stores should be merged.
