# Finviz Dashboard

A personal financial dashboard built on a Finviz Elite subscription.

**Current status:** Phase 1 (Foundation + Stock Lookup) only — ticker search and a
quote table. See [docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md](docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md)
for the full 8-phase roadmap (screener, options, watchlists/alerts, insider feed,
news/sentiment, portfolio tracking are all planned but not built yet).

## Prerequisites

- A [Finviz Elite](https://finviz.com/elite.ashx) subscription (for the export API token)
- Docker and Docker Compose

## Setup

1. Copy the env file and fill in your Finviz Elite token:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and replace `FINVIZ_API_TOKEN` with your real token, found in your
   Finviz Elite account settings under the export/API section.

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
```
