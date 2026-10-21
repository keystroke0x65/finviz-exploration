# Finviz Dashboard

A personal financial dashboard built on a Finviz Elite subscription.

**Current status:** Phase 1 (stock lookup) and Phase 2 milestone 1 (screens + watchlist).
Pattern detection and trade setups (milestones 2–3) are next. See
[the phase 2 design](docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md)
and [the original roadmap](docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md).

## What it does

- **Screens** tab: saved Finviz screens. Paste a Finviz screener URL (build it on
  finviz.com, copy the address bar) or use the form for country, price, float, market cap,
  volume and relative volume. Running a screen shows price, change, after-hours change,
  volume, relative volume, float, market cap and the latest headline, with links to Finviz
  and an "add to watchlist" button. Two screens are created on first start: "Top gainers —
  low float" (feeds the watchlist) and "After-hours".
- **Watchlist** tab: filled automatically from every screen marked "feeds watchlist".
  While the backend runs, the feeder runs every 15 minutes on weekdays from 04:00 to 20:00
  US Eastern (pre-market through after-hours), and keeps one history line per stock per
  day it showed up. Auto-added stocks drop off 90 days after they last showed up; pinned
  and manually added stocks never expire. "Refresh from feeder" runs it immediately.
- **Lookup** tab: single-ticker quote (Phase 1).

Finviz silently ignores filter codes it doesn't recognise, so saving a screen checks any
pasted codes with Finviz first and rejects ones it would ignore.

## Prerequisites

- A [Finviz Elite](https://finviz.com/elite.ashx) subscription (for the export API token)
- Docker and Docker Compose

## Setup

1. Copy the env file and fill in your Finviz Elite token:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and replace `FINVIZ_API_TOKEN` with your real token, found in your
   Finviz Elite account settings under the export/API section. Optional settings:

   | Variable | Default | Meaning |
   |---|---|---|
   | `QUOTE_CACHE_TTL_MINUTES` | 15 | How long a looked-up quote is cached |
   | `FEEDER_INTERVAL_MINUTES` | 15 | Minutes between watchlist feeder runs |
   | `WATCHLIST_RETENTION_DAYS` | 90 | Days after its last feeder hit before an auto-added stock is dropped |
   | `IS_FEEDER_ENABLED` | true | Set to `false` to stop the background feeder |

2. Start the stack:

   ```bash
   docker compose up --build
   ```

3. Open the app:

   - Frontend: http://localhost:5173
   - Backend health check: http://localhost:8000/health

Enter a ticker (e.g. `AAPL`) in the search box to look up a quote.

## Running tests

Backend:

```bash
cd backend
pip install -e ".[dev]"
pytest -v
```

Frontend:

```bash
cd frontend
npm install
npm test
```

## Manually verifying the Finviz integration

`backend/scripts/finviz_sanity_check.py` hits the real Finviz Elite API directly
(not run in CI). Use it after Finviz changes something on their end, or when
debugging an unexpected error from `/api/stocks/{ticker}`:

```bash
cd backend
FINVIZ_API_TOKEN=<your real token> python -m scripts.finviz_sanity_check AAPL
# Screens: runs the default screens and checks Finviz recognises every form code
FINVIZ_API_TOKEN=<your real token> python -m scripts.finviz_sanity_check --screens
```
