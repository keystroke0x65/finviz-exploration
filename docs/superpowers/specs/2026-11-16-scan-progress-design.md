# Scan progress bar

Date: 2026-11-16
Status: approved in chat by the user ("yeah")

## Intent
While a watchlist scan runs, the user wants to see how far along it is: a progress bar on
the Setups tab just above the "Last scan …" line, for scans they start ("Scan watchlist")
and the automatic ones every 15 minutes.

## Goals
- A bar with "N of M stocks", the stock being scanned, and when the scan started.
- Shown for manual and automatic full scans, labelled "Scanning watchlist" / "Automatic scan".
- "Preparing…" while the scan fetches watchlist prices and picks active stocks; "Finishing…"
  while it settles setups of inactive stocks.
- When the scan ends, the bar goes away and the setups list reloads (Claude's call).

## Non-goals
- One-stock scans ("Scan this stock" on the Stock tab) don't show the bar (Claude's call:
  they take seconds and run from another page).
- No history of past scans' progress; no progress after a backend restart.

## Approaches
- **Chosen: in-memory progress + polling.** The backend keeps one progress record (the app
  is one process and scans already take a process-wide lock); `GET /api/scans/progress`
  returns it; the Setups page polls every 2 s.
- Progress in the database (app_meta): a write per stock for nothing the user needs; lost.
- Server push (SSE/websocket): no existing infrastructure, more moving parts; lost.

## Design
- `app/scanning/progress.py`: a thread-safe tracker with `start(kind, started_at)`,
  `set_phase`, `set_total`, `begin_ticker(ticker, index)`, `finish()`, `snapshot()`.
  Phases: `preparing`, `scanning`, `finishing`.
- `run_scan` takes an optional progress reporter (a dependency passed in, not a global
  read inside the scanner) and reports phase changes and each ticker.
- The manual full-scan route and the scheduled scan both start and finish the tracker
  around `run_scan`, with kind `manual` / `automatic`; finish runs even when the scan fails.
- `GET /api/scans/progress` → `{running: false}` or `{running: true, kind, phase,
  done, total, ticker, started_at}`.
- Setups tab: polls every 2 s; shows the bar above the scan status line while running;
  on the change from running to not running, reloads setups and scan status.

## Left to the builder
Exact styling within the current look; poll cleanup details.
