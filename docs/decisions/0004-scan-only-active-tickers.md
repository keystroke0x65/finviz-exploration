# 0004: Scan only the active part of the watchlist, at most 40 tickers
Date: 2026-10-21
Status: accepted

## Context
Pattern scanning needs three bar series per ticker (1m, 5m, daily). The watchlist keeps
auto-added names for 90 days and can grow to hundreds of tickers. Finviz Elite documents
no rate limits; the app paces itself at one request per second, and a live test showed
HTTP 429 once two processes called it at the same time.

## Decision
Each scan fetches one batched price snapshot for the whole watchlist (100 tickers per
request), then fetches bars only for "active" tickers: just found by the feeder, relative
volume ≥ 1.5, or a move of 5% or more (regular or after-hours), most active first, capped
at 40. Bars are cached (1m for 60 s, 5m for 5 min, daily until the next close). On a 429
the scan stops and reports the skipped tickers rather than retrying.

## Alternatives considered
- **Scan the whole watchlist every time**: hundreds of tickers × 3 requests per 15
  minutes, far more than one request per second allows, and most names are quiet.
- **Massive (Polygon) for bars**: higher limits and deeper history, but adds a second data
  provider before it's needed; kept for backtesting later.

## Consequences
- A full scan costs about 2 minutes and at most ~120 bar requests.
- Quiet watchlist names aren't scanned until they move, so their old setups age out.
- Running the sanity script while the backend scans can trigger rate limiting; the
  scripts README says to stop the backend first.
