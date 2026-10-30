# Finviz Dashboard

A personal financial dashboard built on a Finviz Elite subscription.

**Current status:** Phase 2 complete: screens, an auto-fed watchlist, pattern detection
with entry/stop/target plans, a per-stock long/short verdict, outcome tracking with a
track-record view, candlestick confirmation, and a candle chart. See
[the phase 2 design](docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md)
and [the original roadmap](docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md).

## What it does

- The header shows the US market session (pre-market, regular hours, after-hours) on a
  4 AM to 8 PM Eastern strip with a marker for now. Exchange holidays aren't shown.
- **Setups** tab (home): setups found in the latest scans, best score first. Each shows
  the pattern, timeframe (1m, 5m or daily), state (forming = entry not reached yet,
  triggered, extended = already more than 1R past entry; triggered and extended setups
  show when price reached the entry, e.g. "Triggered 9:42 AM" Eastern, or the date for
  daily setups, taken from the bar itself rather than the scan, which runs every 15
  minutes), entry, stop, target, the
  reward:risk actually available, risk as a % of price, and a 0-100 score you can expand
  to see how it was built. Targets are 3R unless a daily support/resistance level sits in
  the way; then the target stops at that level and the row says "capped by level at …".
  The **Sykes** column grades each setup A-F on our version of Tim Sykes's sliding scale:
  his seven P.R.E.P.A.R.E. factors (pattern and price, risk/reward, ease of entry and
  exit, history of spiking, time of day, catalyst, market environment), each good / ok /
  poor. Hover over the grade to see every factor. Click the Sykes header to rank by grade
  (best letter first, then points, then score; ungraded last); click it again to go back
  to score order. Sykes doesn't publish a formula, so the
  thresholds and their sources are in
  `docs/superpowers/specs/2026-10-28-sykes-sliding-scale-design.md`. Each full scan also
  counts US stocks up 30%+ on Finviz for the market factor (one extra request). Setups
  recorded before the grade existed show "—" until they're scanned again.
  Above the table a grey line says when the last full scan ran ("Last scan 3:45 PM · 40
  stocks"); it turns into a red warning if that scan failed, or if no scan has finished for
  30 minutes during scan hours (4 AM-8 PM ET), since the setups shown are then out of date.
  Bearish patterns are listed as warnings; tick "Show short setups" to turn them into
  ranked short setups. Detection is rule-based: it flags shapes worth checking on the
  chart, it doesn't predict, and it isn't advice.
- Tickers in Setups, Screens and the Watchlist are links: click to open the stock here, or
  Ctrl/Cmd-click, middle-click or right-click → "Open link in new tab" to open it in its
  own tab. The address (e.g. `/?stock=HOST`) opens the Stock view on that ticker, and
  stays on the stock you're viewing, so a refresh or a copied link comes back to it.
- **Stock** tab: candles (1m, 5m or daily) with volume bars underneath (green on up
  candles, red on down), daily support/resistance near the price, pre-market high/low,
  previous close and VWAP. On 1m and 5m, pre-market (4:00-9:30 AM ET) is shaded teal and
  after-hours (4:00-8:00 PM ET) purple; Finviz only has bars when a trade happened, so a
  thinly traded stock shows only a sliver of each. The top-left corner shows the open, high,
  low, close, change and volume of the bar under the mouse (the latest bar when the mouse is
  off the chart). Click a setup to draw its entry, stop and target. Tickers anywhere in the app open this tab; the small "Finviz" link opens Finviz.
- **Screens** tab: saved Finviz screens. Paste a Finviz screener URL (build it on
  finviz.com, copy the address bar) or use the form for country, price, float, market cap,
  volume and relative volume. Running a screen shows price, change, after-hours change,
  volume, relative volume, float, market cap and the latest headline (with the date and time it came out, Eastern; older years show the year), with links to Finviz
  and an "add to watchlist" button. Two screens are created on first start: "Top gainers —
  low float" (feeds the watchlist) and "After-hours".
- **Watchlist** tab: filled automatically from every screen marked "feeds watchlist".
  While the backend runs, the feeder runs every 15 minutes on weekdays from 04:00 to 20:00
  US Eastern (pre-market through after-hours), and keeps one history line per stock per
  day it showed up. Auto-added stocks drop off 90 days after they last showed up; pinned
  and manually added stocks never expire. "Refresh from feeder" runs it immediately.
  The tab shows when the feeder last ran and which screens failed (e.g. an expired
  token or Finviz rate limiting); failures are also logged as warnings.
  Each row also shows the stock's latest price, change, after-hours change and relative
  volume from the most recent scan.

### How scanning works

After every feeder run (every 15 minutes, 4:00 AM to 8:00 PM ET on weekdays) the app gets
current prices for the whole watchlist, then scans up to 40 of the most active stocks:
those the feeder just found, or with relative volume of 1.5 or more, or moving 5% or more
(regular or after-hours). For each it loads 1m, 5m and daily bars (cached: 1 minute,
5 minutes, and until the next close), finds daily levels, runs the pattern detectors and
records what it finds. "Scan watchlist" on the Setups tab and "Scan this stock" on the
Stock tab run a scan on demand; a full scan takes about two minutes because Finviz is
called at most once a second. "Scan this stock" skips the 1m/5m bar cache and the quote
cache so it always works from the latest bars, then reloads the chart, verdict, setups and
quote. If Finviz starts rate limiting, the scan stops and lists the
stocks it skipped. Only one scan runs at a time: "Scan watchlist" says so if a scheduled scan is
already running. Expired watchlist entries are cleared on every 15-minute tick, including
evenings and weekends.

Patterns so far:
- Momentum (1m and 5m): high/low of day break, pre-market high/low break, opening range
  breakout/breakdown, red-to-green / green-to-red, VWAP reclaim/rejection, ABCD / inverse
  ABCD, micro pullback, first pullback after a gap up / first bounce fail after a gap down.
- All timeframes: bull/bear flag, flat-top breakout / flat-bottom breakdown, ascending /
  descending triangle, double bottom / double top, bull/bear pennant, symmetrical triangle
  (called toward the edge price is near), falling / rising wedge, range breakout /
  breakdown, cup and handle / inverted cup and handle.
- Reversals (5m and daily only): head and shoulders / inverse, triple top / bottom,
  rounding top / bottom.

Candlestick signals (engulfing, hammer / shooting star, morning / evening star, doji) never
create setups on their own. A supporting candle whose wick tags a setup's stop or entry adds
5 points to its score; an opposing candle at its entry takes 5 away.

### Track record

The **Track record** tab shows how each pattern has actually played out on your stocks, per
timeframe, filterable by float size and session: number of trades, win rate, average R,
average win (so a high win rate made of tiny capped wins is visible), the average best move
after entry, how many stocks the trades came from, and over how many trading days (hover for
the dates). Only trades you could have taken count: a setup counts once price reached its
entry, then it scores its reward:risk if it hit the target, −1R at the stop, and 0R if it
expired (the exit price isn't recorded). The same pattern re-detected on the same stock and
exiting on the same bar counts as one trade. Setups that never filled, were first seen already
past entry, or lost their bars are listed separately.

Once a pattern has 30 or more trades on a timeframe, from at least 5 different trading days,
its average R moves each new setup's score by up to 15 points either way, and the score
details say so. Until then the history is shown (muted) but doesn't affect scores.

### The verdict

Every scanned stock also gets one overall call: **Leans long**, **Leans short** or **No
clear edge**, with the reasons listed on the Stock tab (and on hover elsewhere). It
combines four things, each shown in the reasons:
- trend: price against VWAP, the 9 and 20 EMAs on 1m and 5m, and the 20- and 50-day
  averages;
- volume: whether recent 1m volume is heavier on up bars or down bars, counted for less
  when relative volume is low;
- room: distance to the nearest daily resistance above versus support below (each side
  counted up to 20%, so a stock with nothing overhead isn't marked down for distant support);
- patterns: bullish versus bearish patterns found, weighted by quality.

"No clear edge" is common and means the signals disagree; the app doesn't force a call.
It is also the answer when there's too little data (e.g. only the daily trend) or when the
trend and the patterns point strongly in opposite directions.
Inputs it doesn't have (e.g. no trades yet today) are left out and named in the reasons.
The verdict is shown even when short setups are hidden.

Every setup is recorded and later marked as having hit its target or stop first, expired
(intraday setups at 8:00 PM ET, daily ones after 20 sessions), or unresolved (Finviz no
longer had the bars). These outcomes will feed a track-record view in a later milestone.

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

   If port 5173 is already used by another dev server, set `FRONTEND_PORT=5174` (or any
   free port) in `.env` and use that port below.

3. Open the app:

   - Frontend: http://localhost:5173
   - Backend health check: http://localhost:8000/health

Enter a ticker (e.g. `AAPL`) in the search box to look up a quote.

## Where the data lives

Everything is stored in one SQLite file, `data/finviz_dashboard.db`, inside this project
folder (the folder is gitignored apart from a placeholder). Back it up by copying the
file; delete it to start fresh (the default screens are recreated on the next start).
Docker runs the backend as user `1000:1000` so the file stays owned by you; set
`HOST_UID`/`HOST_GID` in `.env` if your user id differs (`id -u`, `id -g`).

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
# Bars: fetches 1m/5m/daily bars for a ticker and runs a full scan of it
FINVIZ_API_TOKEN=<your real token> python -m scripts.finviz_sanity_check --bars HOST
```
