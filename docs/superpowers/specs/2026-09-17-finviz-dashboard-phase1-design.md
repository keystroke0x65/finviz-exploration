# Finviz Dashboard — Project Roadmap & Phase 1 Design

Status: approved pending final user review
Date: 2026-09-17

## Background

The user has a Finviz Elite subscription and wants a personal financial dashboard to
explore what it makes possible: stock lookup, screening, and eventually options-related
tooling built on top of Finviz's fundamental/technical data. The project serves two
goals about equally: genuine day-to-day research use, and a vehicle for learning
(financial APIs and data are new territory for the user, who is otherwise an
experienced software engineer).

Two facts materially shaped the design:

- **Finviz Elite has no options data whatsoever** — no chains, no IV, no greeks, on any
  tier. Any options feature needs a second data source.
- The user has a **Schwab (thinkorswim) brokerage account**, and Schwab's developer API
  provides options chains and greeks for free with a brokerage account — chosen as that
  second source. The developer app approval process can take several days, so it's
  sequenced early enough not to block later phases.

Deployment target is **local-only, single-user** — no auth, no cloud hosting for now.

## Full Roadmap (for context; only Phase 1 is speced in detail here)

Each phase gets its own brainstorm → spec → implementation-plan cycle when we get to it.

1. **Foundation + Stock Lookup** — project scaffold, Finviz Elite export API client,
   single-stock quote lookup. Everything else depends on this.
2. **Screener** — Finviz screener export integration, filter UI, saved queries (doubles
   as the base for watchlists later).
3. **Options** — Schwab API auth (start the developer application early — it's slow),
   options chain viewer tied to a looked-up stock.
4. **Watchlists + Alerts** — persistence for saved tickers/queries, threshold rules,
   notification delivery.
5. **Options Strategy Suggestions** — ranks candidates (e.g. covered calls, spreads)
   using combined screener output (phase 2) and chain data (phase 3).
6. **Insider / Institutional Activity Feed** — surfaces Finviz Elite's insider
   transaction data per ticker/watchlist.
7. **News + Sentiment** — Finviz's per-ticker news aggregation, plus a sentiment layer.
8. **Portfolio Tracking & Backtesting** — Schwab position sync, P&L tracking, and
   backtesting screener-based strategies against history. Deliberately last: it's the
   most complex phase and depends on patterns established by everything before it.

Rationale for this order: the two biggest unknowns — Finviz's export API shape and
Schwab's API auth/approval — are front-loaded (phases 1 and 3) so we hit surprises
early rather than late in the project.

## Phase 1: Foundation + Stock Lookup

### Architecture

```
┌─────────────────┐      ┌──────────────────────┐      ┌─────────────────┐
│  React frontend │ ───▶ │  FastAPI backend      │ ───▶ │  Finviz Elite    │
│  (Vite + TS)    │ ◀─── │  (Python)             │ ◀─── │  Export API      │
└─────────────────┘      │                       │      └─────────────────┘
                          │  - finviz_client       │
                          │  - SQLite (cache)      │
                          └──────────────────────┘
```

- The backend owns all external API calls. The frontend never talks to Finviz directly
  — this keeps the Elite API key server-side only, never shipped to a browser. This
  same rule will apply to the Schwab API in phase 3.
- Dev environment runs via **Docker Compose** (backend, frontend, and a volume-mounted
  SQLite file as services), per explicit user preference over running plain local
  processes.

### Finviz Elite integration (domain notes — new territory for the user)

Finviz's "API" is not a typical REST/JSON service. It's a set of **CSV export
endpoints** gated by an Elite auth token, e.g.
`export.finviz.com/export.ashx?v=...&f=...&auth=YOUR_TOKEN`.

Key differences from a typical web API:

- **Responses are CSV text**, not JSON — parsed with pandas.
- **Filters are positional/coded strings**, not named query params (e.g.
  `f=cap_large,sec_technology`). Finviz's own screener UI is effectively the reference
  for what the codes mean. A mapping layer (human-readable filter names → Finviz codes)
  lives inside the client module so the rest of the app never handles raw codes.
- **No documented rate limits** — the client is defensive by default: caches
  aggressively and paces requests conservatively rather than probing for the limit.
- **Auth is a single static token** in the URL from the user's Elite account settings,
  not OAuth. It's a secret: lives in `.env` (gitignored), never committed, never sent
  to the frontend.

The backend exposes a `finviz_client` module wrapping this entirely: the rest of the
app calls typed Python functions (`get_quote(ticker)`, later `run_screener(filters)`)
and never touches CSV parsing or URL-encoding details directly.

### Data model (Phase 1)

SQLite, single table for now:

- `quote_cache(ticker TEXT, data JSON, fetched_at TIMESTAMP)` — cached parsed quote
  response. Cache expires after a configurable TTL (default 15 minutes — reflects that
  this is a research tool, not a trading terminal requiring tick-level freshness).

Later phases add tables for saved screens, watchlists, alerts, portfolio positions,
etc. — not created now (YAGNI).

### API surface (Phase 1)

- `GET /api/stocks/{ticker}` → quote + key fundamentals/technicals for one ticker
  (price, day change, volume, market cap, P/E, sector, and whatever else Finviz's
  quote export provides).
- `GET /api/stocks/{ticker}/refresh` → bypass cache and force a fresh fetch.

### Frontend (Phase 1)

- Single search box → ticker lookup → a quote detail view rendered as a stats table.
- No charts yet. Deliberately deferred so the full pipeline (Finviz → backend → cache →
  frontend) is validated end-to-end as fast as possible; a chart is a natural
  phase-1.5/phase-2 addition once the plumbing works.

### Error handling (finance-specific)

Because this is a tool the user may act on, errors must be explicit rather than
silently returning empty/misleading data:

- **Invalid ticker** — Finviz returns an empty CSV for unknown symbols; surfaced to the
  user as "ticker not found," not a blank screen.
- **Delisted / no data** — distinguished from a typo where possible.
- **Finviz auth failure** (expired/incorrect token) — a distinct, actionable error, not
  conflated with "ticker not found."

### Testing

- Backend unit tests mock the Finviz HTTP layer — no live external calls in CI.
- A manual `scripts/` sanity script hits the real Elite API, for confirming the
  integration still works when Finviz changes something on their end (undocumented
  APIs drift silently).

### Explicitly out of scope for Phase 1

- Screener (phase 2)
- Any options data (phase 3+, requires Schwab)
- Auth/multi-user support (not needed — local-only single-user)
- Charts (deferred, see Frontend section above)
- Watchlists, alerts, portfolio, news, insider data (later phases)

## Project conventions

This project already has `.claude/rules/*.md` house-style guides (naming, testing,
error handling, secrets handling, commit conventions, dependency addition, etc.) —
implementation should follow those rather than introducing new conventions.
