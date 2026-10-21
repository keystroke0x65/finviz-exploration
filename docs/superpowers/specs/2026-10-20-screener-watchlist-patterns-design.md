# Phase 2 Design — Screens, Momentum Watchlist, Pattern Setups

Status: approved 2026-10-20
Date: 2026-10-20

## Intent

The user trades small-cap momentum: cheap, low-float US stocks with unusual volume that
are moving, often in after-hours. Today the whole workflow happens on Finviz Elite:

1. Run a screen (e.g. US, price under $20, float under 10M, top % gainers; or rel vol 2x+,
   volume 1M+; after-hours: US, under $20, float under 20M, market cap under $200B).
2. For each hit: read the latest news, open the 2-year daily chart, draw support and
   resistance lines, then watch how 1-minute and 5-minute candles react to those lines.

Finviz already does screening, news and charts well. **This app earns its place by doing
the analysis step the user does by hand**: find the popular chart patterns on each
candidate, say whether each is bullish or bearish, propose entry / stop / target for a
3:1 reward-to-risk trade, and **rank** the setups, since most won't offer a clean 3:1.

A second reason: momentum names often run for ~3 days, die, then come back a week or
months later. The app keeps a **watchlist built automatically from recent top gainers**
so those names keep getting scanned after they drop off today's screen.

## Goals

- Saved, editable screens (the user's filters change often), runnable on demand.
- A watchlist fed automatically from a "feeder" screen (top gainers), that the user can
  also add to and remove from by hand.
- A pattern scanner over watchlist + current screen hits on 1m, 5m and daily bars.
- **The user trades long only today, but plans to short one day.** Each bullish setup
  gets pattern name, entry, stop, 3R target, and the reward:risk actually available
  before the next daily resistance level.
- Bearish patterns are detected and shown as **warnings** ("bear flag on 5m"): not ranked
  as setups. The user wants to know when something looks like a short, to avoid it or
  wait.
- **Everything is built direction-aware** so short setups can be switched on later:
  detectors report direction, and trade-plan and ranking code handle both directions and
  are tested both ways. A "Show short setups" setting (off by default) turns bear
  warnings into full ranked short setups.
- A ranked list of setups, with the reasons behind each score visible.
- **One verdict per stock**: leans long, leans short, or no clear edge, with its reasons.
  Patterns are one input; trend, levels and volume are the others. The user's real
  question is "long or short, and where in and out", not "which patterns exist".
- **Outcome tracking**: every flagged setup is recorded and later resolved (target or
  stop first), so the user learns which patterns actually work on their kind of stocks,
  and the ranking can lean on that track record.
- A chart per setup showing the candles, the pattern, entry/stop/target and the daily
  levels, so the user can check the call in seconds; plus a link out to Finviz for news
  and their own drawings.

## Non-goals (this phase)

- Alerts / notifications (later phase).
- Backtesting how patterns performed historically (needs deeper intraday history; see
  "Data sources").
- Drawing tools. The user keeps drawing on Finviz.
- Options, Schwab, news sentiment.

## Anti-goals

- **Never place or stage orders.** This is analysis only.
- Never suggest a short trade while "Show short setups" is off. With it off, bearish
  patterns are information only.
- Never present a setup without its stop and actual reward:risk. A "3:1" that runs into
  resistance at 1.2R must show 1.2R.
- No black-box score. Every rank must be explainable from the numbers shown next to it.
- Don't hammer Finviz. Its export API has no documented rate limits and the user's Elite
  account is the only one they have.

## Data sources (verified 2026-10-20 against the user's Elite account)

All from Finviz Elite, auth token in `FINVIZ_API_TOKEN`. CSV responses.

| Need | Endpoint | Verified result |
|---|---|---|
| Screen results | `elite.finviz.com/export.ashx?v=111&f=<filters>&s=<signal>` | US / <$20 / float <10M / `s=ta_topgainers` → 29 rows |
| Wide columns per ticker | `export.ashx?v=152&t=<tickers>&c=<column ids>` | Includes Shares Float, Relative Volume, Average Volume, After-Hours Close, After-Hours Change, latest news title + URL |
| Daily bars | `elite.finviz.com/quote_export.ashx?t=<ticker>&p=d` | ~10 years, columns Date, Open, High, Low, Close, Volume |
| 1-minute bars | `quote_export.ashx?t=<ticker>&p=i1` | ~2 weeks, 4:00 AM–8:00 PM (pre-market + after-hours included) |
| 5-minute bars | `quote_export.ashx?t=<ticker>&p=i5` | ~3 weeks, same hours |

Domain quirks the builder must handle (and document in code):

- `export.ashx` and `quote_export.ashx` both redirect (to `/export` and `/quote_export`);
  following redirects is fine. Phase 1's client already uses `/export/screener`.
- Intraday timestamps look like `10/20/2026 19:59 PM`: a 24-hour clock with a redundant
  AM/PM suffix. Parse the 24-hour part and ignore the suffix. Times appear to be US
  Eastern (session starts 04:00); confirm with the sanity script.
- Daily dates are `MM/DD/YYYY`.
- **Unknown filter or signal codes are silently ignored, one by one**: Finviz drops a
  code it doesn't recognise (typo, or a value it doesn't offer such as `sh_price_u17`)
  and applies the rest, with no error. A typo next to valid filters just widens the
  screen, so row counts can't reveal it (and valid broad screens are large anyway: US
  only is ~10,400 rows; the whole market ~11,750). So: when a screen is saved, each
  pasted extra code and the signal is checked on its own against the whole-market count;
  one that doesn't narrow it is rejected, naming the code. The sanity script checks every
  code the form can produce the same way. (Corrected 2026-10-20 after a live check; an
  earlier draft flagged results over 5,000 rows instead.)
- Wide-column exports (`v=152&c=<ids>`) return columns in ascending id order regardless
  of the order requested, and omit `No.` unless id 0 is requested. Map columns by header
  name, not position.
- Units: `Market Cap` and `Shares Float` are in millions; `Average Volume` is in
  thousands; `Volume` is a raw share count. Percent columns include a `%` sign.
- `t=` accepts several comma-separated tickers in one call (verified with 4).
- Verified codes: `geo_usa`, `sh_price_u20`, `sh_float_u10`, `sh_float_u20`,
  `cap_largeunder`, `sh_relvol_o2`, `sh_curvol_o1000`, signal `ta_topgainers`, order
  `-change`. Column ids: Ticker 1, Company 2, Country 5, Market Cap 6, Shares Float 25,
  Average Volume 63, Relative Volume 64, Price 65, Change 66, Volume 67, After-Hours
  Close 71, After-Hours Change 72, News Time 135, News URL 136, News Title 137.

**Massive (Polygon.io) is not used in this phase.** The user has a subscription and keys
in `.env` (`MASSIVE_API_KEY`, `MASSIVE_S3_*`). It becomes relevant for backtesting
(deeper intraday history) or if Finviz rate limits block scanning. Leave the keys unused.

## How it works

### 1. Screens

- A screen = name + Finviz filter codes (`f=`) + optional signal (`s=`, e.g.
  `ta_topgainers`) + optional order (`o=`). Stored as raw Finviz codes, since there are
  hundreds and the user already thinks in Finviz terms.
- Two ways to create/edit:
  - **Paste a Finviz screener URL**: the app extracts `f`, `s`, `o`. This is the main path;
    the user builds the screen on Finviz and pastes it.
  - **A small form** for the filters the user named (country, price under, float under,
    market cap under, volume over, relative volume over, top gainers). The form edits the
    same codes. Unknown codes from a pasted URL are kept and shown as-is.
- Seed two screens on first run (editable/deletable): "Top gainers — low float" (US,
  under $20, float under 10M, top gainers) and "After-hours" (US, under $20, float under
  20M, market cap under $200B). Exact codes verified by the builder.
- Running a screen returns a table: ticker, company, price, change %, after-hours change
  %, volume, rel vol, float, market cap, latest news headline (links to the article), and
  actions: "Open on Finviz", "Add to watchlist", "Scan".

### 2. Watchlist

- One watchlist. Each entry: ticker, source (`auto` or `manual`), date added, last date
  it appeared in the feeder screen, and its appearance history (date + change % that day),
  so the user can see "ran Oct 3–5, back today".
- **Feeder:** one or more screens are marked "feeds watchlist". The seed "Top gainers —
  low float" screen is the feeder by default.
- **When the feeder runs (my call):** a background job in the backend runs the feeder
  every 15 minutes on weekdays between 4:00 AM and 8:00 PM ET, while the app is running.
  Every hit is added (or its "last seen" updated). Also runs when the user clicks
  "Refresh". The app only runs when Docker is up, so days it's off are simply missed.
- **Retention (my call):** auto-added names drop off 90 days after they last appeared in
  the feeder. Reappearing resets the clock. Manually added names never expire. Any entry
  can be pinned to stop it expiring.
- **Removal (my call):** removing a name deletes it. If it tops the feeder again later, it
  comes back as a new auto entry (that comeback is exactly what the watchlist is for).
- Manual add: type a ticker; validated against Finviz (Phase 1's quote lookup).

### 3. Pattern scanning

Detection is rule-based. It flags price shapes that match defined rules; it does not
predict. The UI says "detected", not "will".

**Daily levels (support/resistance):** from the last 2 years of daily bars, find swing
highs/lows, cluster nearby ones into price levels, and keep levels by how many times
price touched them. These stand in for the lines the user draws by hand. They're drawn
on every chart and used to cap targets.

**Patterns.** The user wants the full catalogue. Bull patterns produce trade setups; bear
patterns produce warnings (or short setups when that setting is on). "Either" means the
direction is set by which way price breaks.

*Core (milestone 2; runs on 1m, 5m and daily):*

| Pattern | Bull | Bear |
|---|---|---|
| Flag | bull flag | bear flag |
| Horizontal level break | flat-top breakout | flat-bottom breakdown |
| Triangle | ascending | descending |
| Double | double bottom | double top |

*Momentum day-trading (milestone 2; intraday bars only):*

| Pattern | Bull | Bear |
|---|---|---|
| ABCD | ABCD | inverse ABCD |
| Micro pullback | micro pullback | — |
| First pullback after gap | first pullback (gap up) | first bounce fail (gap down) |
| VWAP | VWAP reclaim | VWAP rejection |
| High/low of day | high-of-day break | low-of-day break |
| Pre-market level | pre-market high break | pre-market low break |
| Opening range | opening range breakout | opening range breakdown |
| Previous close | red-to-green | green-to-red |

*Continuation (milestone 3):*

| Pattern | Bull | Bear |
|---|---|---|
| Pennant | bull pennant | bear pennant |
| Symmetrical triangle | either | either |
| Wedge | falling wedge | rising wedge |
| Rectangle / range | range breakout | range breakdown |
| Cup | cup and handle | inverted cup and handle |

*Reversal (milestone 3; best on 5m and daily):*

| Pattern | Bull | Bear |
|---|---|---|
| Head and shoulders | inverse head and shoulders | head and shoulders |
| Triple | triple bottom | triple top |
| Rounding | rounding bottom | rounding top |

*Candlestick signals (milestone 3): not setups on their own.* Bullish/bearish engulfing,
hammer/shooting star, morning/evening star, doji. They fire too often to stand alone, so
they adjust the score of a setup (or warning) when they appear at its key level: a
bullish signal at a bull setup's entry or support raises it, a bearish one lowers it.

Momentum-pattern reference points (my calls, each configurable):
- VWAP is anchored at the 4:00 AM ET pre-market open, computed from 1m bars.
- Opening range = first 5 minutes of the regular session (9:30–9:35 ET).
- High/low of day uses the regular session; pre-market high/low are separate levels.
- Previous close comes from daily bars.

**Detector interface.** With 40+ detectors this is worth one shared shape: each detector
is a plain function `(bars, context) -> list[PatternMatch]`, registered in a list, where
`context` carries daily levels, VWAP, previous close and session times. Adding a pattern
means writing one function plus its tests. No plugin system or classes.

Exact detection rules (pole size, consolidation length/tightness, touch tolerance,
volume behaviour) are left to the builder, but each detector must:
- be a pure function of a bar series, unit-tested with hand-built bar fixtures (a clean
  example, a near-miss that must not match, an invalidated one);
- return a quality score 0–1 with the sub-measures that produced it;
- return the key price points (pattern bounds) so the chart can draw it.

**Setup state:** `forming` (entry not yet hit), `triggered` (price beyond entry, stop not
hit, less than 1R of progress), `extended` (more than 1R past entry: shown but ranked
down), `invalidated` (stop hit: not shown).

Bear matches use the same states (`forming` = not yet broken down, `triggered` = broken
down).

### 4. Trade plan per setup

Computed for both directions; bear plans are shown only when "Show short setups" is on.

For a long (bull) setup:

- **Entry** = the breakout level (flag high, resistance line, neckline).
- **Stop** = the pattern's invalidation point (flag low, last higher low, etc.).
- **Risk (R)** = entry − stop.
- **3R target** = entry + 3 × R.
- **Available reward:risk** = if a daily resistance level sits between entry and the 3R
  target, (that level − entry) / R; otherwise 3.0.
- Show all of these, plus risk as a % of price (a $0.10 stop on a $2 stock is 5%).

**Exit options.** The fixed 3R target is the baseline plan. Alongside it, show:
- partial-profit levels at 1R and 2R;
- a trailing stop suggestion: below the most recent higher low on the setup's timeframe
  (my call; the builder may add a 9 EMA trail as a second option).

For a short (bear) setup, mirror it: entry = breakdown level, stop = invalidation above,
target = entry − 3R, capped by the next daily *support* below.

Shorting small caps has extra constraints the app should eventually show next to short
setups (domain notes for later, not built now): whether the stock can be borrowed
(Finviz's `Shortable` column; locates on low floats are often unavailable or expensive),
the SEC short sale restriction (SSR, Reg SHO Rule 201) that applies after a 10% drop from
the prior close and lasts into the next day, and short float (squeeze risk).

### 5. Ranking

Score each setup from visible parts (exact weights are the builder's call, but the
breakdown must be shown in the UI):

- available reward:risk (biggest factor; no extra credit above 3);
- pattern quality (from the detector);
- volume confirmation (relative volume; volume behaviour inside the pattern);
- freshness: `forming` / just `triggered` rank above `extended`;
- timeframe agreement: bonus when bullish patterns show on more than one timeframe;
- conflicting pattern (my call): an active opposite-direction pattern on the same ticker
  on the same or a higher timeframe ranks the setup down, and the conflict is shown on
  the row;
- candlestick confirmation at the setup's key level (milestone 3);
- track record (my call): once a pattern + timeframe has at least 30 resolved outcomes,
  its actual win rate and average R feed the score. Below 30, it's ignored and the row
  says "not enough history".

### 5a. Per-stock verdict

Each scanned stock gets one verdict: **leans long**, **leans short**, or **no clear
edge**, plus a short list of the reasons. Inputs (my call; weights are the builder's,
but every input's contribution is shown):

- **Trend**: price vs VWAP; price vs 9 and 20 EMA on 1m and 5m; daily trend (price vs 20
  and 50 day moving averages).
- **Location**: distance to the nearest daily support below and resistance above,
  expressed in R of the best setup (room to run vs about to hit a ceiling).
- **Volume**: relative volume; whether volume is higher on up bars than down bars in the
  recent intraday window.
- **Patterns**: active long vs short matches, weighted by quality and track record.

"No clear edge" is a real answer and should be common; the app must not force a call.
The verdict is shown on the Setups and Watchlist rows and at the top of the Stock view.
The verdict is direction-aware like everything else: "leans short" is shown even with
short setups off, since the user wants to know.

### 5b. Outcome tracking

- Every setup and warning the scanner flags is stored when first detected (deduplicated
  by ticker + pattern + timeframe + entry level), with its full trade plan and the
  verdict at that moment.
- A resolver, run after each scan, checks later bars and records the outcome: **target**
  (3R or capped target hit first), **stop** (stop hit first), or **expired** (neither:
  intraday setups at 8:00 PM ET the same day, daily setups after 20 sessions).
- If target and stop fall inside the same bar, record **stop** (my call: conservative,
  since bar data can't say which came first).
- Also record maximum favourable and adverse excursion in R. That lets the stats compare
  "fixed 3R" against "take partials at 1R/2R" without simulating every exit style.
- Bear patterns are tracked as short setups even while shorts are hidden, so the history
  is there when the user starts shorting.
- Collection starts in milestone 2, since useful stats need weeks of data. Finviz keeps
  only ~2 weeks of 1m bars, so the resolver must run regularly (it runs with every feeder
  job) or intraday outcomes become unresolvable; mark those as **unresolved** rather
  than guessing.
- Later (not this phase): backtest the same detectors over months of Massive history to
  fill the stats without waiting.

### 6. Scan scope and pacing (my call)

The watchlist can grow to hundreds of names; fetching three bar series for each on every
scan would be thousands of requests. So:

1. One wide-columns screener call (or a few, batched) gets today's change, rel vol and
   after-hours change for every watchlist name.
2. Bars are fetched only for "active" names: in any current screen result, or rel vol
   ≥ 1.5, or |change| ≥ 5% (regular or after-hours). Cap 40 names per scan; the most
   active go first.
3. Requests are paced at no more than 1 per second; back off and surface an error on HTTP
   429 or repeated failures.
4. Bar cache in SQLite: 1m bars valid 60 s, 5m bars 5 min, daily bars until the next
   session.

Scans run when the user clicks "Scan" (whole active set or one ticker), and automatically
after each feeder run.

### 7. UI

Five views (navigation approach is the builder's call; avoid a new dependency if simple
state works). The fifth is **Track record**: per pattern × timeframe, number of
outcomes, win rate, average R, average max favourable excursion, filterable by float
bucket and session (pre-market / regular / after-hours).

- **Setups** (home): ranked table with ticker, pattern, timeframe, state, entry, stop,
  target, available R:R, risk %, score with breakdown on hover/expand, and a warning
  badge when the ticker has a bear warning. A separate "Bearish warnings" list below
  shows tickers with active bear patterns (pattern, timeframe, breakdown level). With
  "Show short setups" on, short setups join the ranked table with a direction column.
- **Screens**: list, run, edit (URL paste + form), mark as feeder.
- **Watchlist**: entries with source, last seen, appearance history, pin, remove, add.
- **Stock**: candle chart (switch 1m / 5m / daily) with daily levels, pattern outline and
  entry/stop/target lines; its setups and bear warnings; Phase 1 quote table; latest
  headline; "Open on
  Finviz" (`https://finviz.com/quote.ashx?t=<ticker>`).

Chart library (my call): TradingView **lightweight-charts** (Apache-2.0, small, built for
candles and horizontal price lines). Record the choice in `docs/decisions/`.

## Architecture

Extends Phase 1; same layering rules (`.claude/rules/`).

```
frontend (React)  ──▶  FastAPI routes  ──▶  services (plain functions)  ──▶  finviz_client
                                               │                              (HTTP + CSV only)
                                               ├── patterns/ (pure detectors + trade plan + ranking)
                                               └── storage (SQLite: screens, watchlist, bar cache)
                         background job (feeder + scan), started in FastAPI lifespan
```

- `finviz_client` gains `run_screen(filters, signal, order)`, `get_columns(tickers,
  columns)` and `get_bars(ticker, interval)`. Still the only module that knows Finviz
  URLs and codes.
- Pattern code has no I/O: bars in, setups out. Tested without network or database.
- Background job takes its clock as an argument so time-window logic is testable.

### Data model (SQLite)

- `screens(id, name, filters, signal, sort_order, feeds_watchlist, created_at, updated_at)`
- `watchlist_entries(ticker PK, source, added_at, last_seen_in_feeder_at, is_pinned)`
- `watchlist_appearances(ticker, seen_on DATE, change_percent, screen_id)`; one row per
  ticker per day per feeder screen.
- `bar_cache(ticker, interval, fetched_at, bars JSON)`
- `setup_records(id, ticker, pattern, direction, timeframe, detected_at, session, entry,
  stop, target, capped_target, quality, score, verdict, float_at_detection, state,
  outcome, resolved_at, max_favorable_r, max_adverse_r)`: outcome is one of `open`,
  `target`, `stop`, `expired`, `unresolved`. Also serves as "latest scan results".

Phase 1 creates tables with `CREATE TABLE IF NOT EXISTS`; keep that approach unless the
schema needs a real migration.

### API (sketch; builder may refine)

- `GET/POST /api/screens`, `PUT/DELETE /api/screens/{id}`, `POST /api/screens/{id}/run`,
  `POST /api/screens/parse-url`
- `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`,
  `PATCH /api/watchlist/{ticker}` (pin)
- `GET /api/bars/{ticker}?interval=1m|5m|daily`
- `POST /api/scans` (all active, or `{ticker}`), `GET /api/setups` (latest, ranked),
  `GET /api/stocks/{ticker}/setups`, `GET /api/stocks/{ticker}/verdict`
- `GET /api/track-record?pattern=&timeframe=&float_bucket=&session=`

All request bodies and query params validated with Pydantic models; tickers use Phase 1's
pattern.

## Errors

Same principle as Phase 1: never show empty or misleading data silently.

- Finviz auth failure, rate limiting and timeouts are distinct, visible errors.
- A scan that couldn't fetch some tickers lists them ("12 scanned, 3 failed: …").
- Saving a screen with a code Finviz doesn't recognise is rejected, naming the code.
- Stale data is labelled with its fetch time.

## Testing

- Detectors, trade plan and ranking: unit tests on hand-built bar fixtures.
- Finviz client: mocked HTTP (as in Phase 1), including the odd intraday timestamp format.
- Watchlist retention / feeder window: tests with an injected clock.
- Verdict: fixture stocks that must come out leans long, leans short, and no clear edge.
- Resolver: target-first, stop-first, same-bar (records stop), expiry, and missing bars
  (records unresolved).
- Extend `backend/scripts/finviz_sanity_check.py` to hit the new endpoints for real.

## Delivery order (my call)

Three milestones, each usable on its own, each with its own implementation plan:

1. **Screens + watchlist**: screens CRUD + URL paste, run screen, feeder job, watchlist
   with retention/pin/manual edits. Useful immediately as a "where are past runners now"
   list.
2. **Bars + core and momentum patterns + setups**: bar fetching and cache, daily levels,
   VWAP, EMAs and session levels, detector interface, core + momentum detectors,
   direction-aware trade plans with exit options and ranking, per-stock verdict, outcome
   recording and resolver, "Show short setups" setting, Setups and Stock views with
   charts.
3. **Continuation, reversal and candlestick patterns + track record**: more detectors on
   the same interface, candlestick score adjustments, the Track record view, and track
   record feeding the ranking (by then there's data).

## Roadmap impact

This replaces the original Phase 2 ("Screener") and pulls the watchlist part of the
original Phase 4 forward. Alerts stay in Phase 4. The pattern/setup work is new; it's a
closer fit to how the user trades than the original Phase 5 (options strategies), which
may be worth revisiting with the user after this ships.

## Left to the builder

Exact pattern rules and score weights; navigation approach; whether to persist scan
results; exact Finviz column ids and filter codes (verify via sanity script); API shape
details beyond the sketch.
