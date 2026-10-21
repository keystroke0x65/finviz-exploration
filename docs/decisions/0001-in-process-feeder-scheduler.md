# 0001: Run the watchlist feeder as an in-process asyncio task
Date: 2026-10-20
Status: accepted

## Context
The watchlist must pick up new top gainers every 15 minutes between 04:00 and 20:00 ET on
weekdays. The app is local-only and single-user, runs as one FastAPI process under Docker
Compose, and stores everything in one SQLite file.

## Decision
A single asyncio task started in FastAPI's lifespan (`app/watchlist/scheduler.py`) loops
forever: run one feeder tick in a worker thread if inside the window, then sleep for
`FEEDER_INTERVAL_MINUTES`. Each tick opens its own SQLite connection. Any unexpected error
in a tick is logged and the next tick tries again. `IS_FEEDER_ENABLED=false` turns it off.

## Alternatives considered
- **APScheduler**: cron-style triggers and missed-run handling, but a new dependency for
  one fixed-interval job.
- **OS cron / a separate container** calling `POST /api/watchlist/refresh`: survives app
  restarts better, but adds a second moving part to set up on WSL/Docker, and the window
  logic would live outside the app.

## Consequences
- No new dependency; the window and retention rules are tested in plain Python.
- Runs only while the backend is up: days when Docker is off are simply missed (accepted
  in the spec).
- With uvicorn `--reload` or several workers there would be one loop per process; fine for
  the current single-process setup, revisit if that changes.
