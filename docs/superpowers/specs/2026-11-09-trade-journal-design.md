# Trade journal

Date: 2026-11-09
Status: draft, ready for the user's review

Items marked **(Claude's call)** were not decided by the user; check those first.

## Intent

The user trades small-cap momentum stocks from thinkorswim and picks trades from this app:
Setups first (high score, A–B Sykes grade, acceptable risk %), then the Stock page's chart.
They want a record of **every decision**: trades they took with their real account, and
setups they looked at and passed on, with the reason. The point is to learn from it: what
they trade, how it pays, which mistakes cost money, and whether their passes were right.

Logging must be fast. The user logs by hand from the Stock page's chart (no broker import),
and wants each trade to keep its chart so it can be reviewed later with every fill marked.

## Goals

1. **Pass** on a stock in two clicks from the Stock page, with one or more reasons from a
   fixed list.
2. **Log a trade** from the Stock page: fills entered by clicking a candle or typing, any
   number of buys and sells (scaling in and out), long or short.
3. Save the 1-minute bars (4:00 AM–8:00 PM ET) for every day a trade was open, so its chart
   survives after Finviz drops them.
4. A **Journal** tab: list of trades and passes, a summary for a chosen period, and each
   entry's saved chart with fills marked.
5. Learning features the user asked for (all in the first version):
   plan vs. actual, mistake chips, what happened after you sold, P&L by time of day,
   keyboard shortcuts, CSV export, position-size calculator, daily max-loss warning, and
   your results compared with the system's track record per pattern.

## Non-goals

- Importing fills from thinkorswim or any broker, and any Schwab API work.
- Saving a picture of the chart automatically (the chart is redrawn from saved bars; a
  "Save as image" button exports one on demand).
- Logging from the Setups tab (the user logs from the chart). Can come later.
- Changing how setups are detected, scored or graded.
- The UI redesign discussed on 2026-10-31 (parked; separate piece of work). The new tab
  follows the current look.
- Multiple accounts, currencies other than USD, options.

## Anti-goals (a failure even if it works)

- Logging that takes longer than placing the trade: more than ~30 seconds for a simple
  in-and-out, or required fields the user has to hunt for.
- Numbers that are quietly wrong: P&L, R or averages computed differently from what the
  page says, or stats that mix trades and passes.
- Losing a trade's chart because bars weren't saved in time, without telling the user.
- A logged trade lost because a Finviz call failed. The journal entry must save even when
  Finviz is down.

## Constraints

- Existing stack: FastAPI + SQLite (`data/finviz_dashboard.db`, schema in `backend/app/db.py`,
  new columns via `ADDED_COLUMNS`), React + TypeScript (Vite) + lightweight-charts v4,
  Docker Compose. No new dependencies needed: CSV via Python's `csv` module, charts via
  lightweight-charts (line + histogram series, `setMarkers`), image export via
  `chart.takeScreenshot()`.
- Finviz keeps only about 2 weeks of 1-minute bars (`get_bars(ticker, "1m")`), so bars must
  be saved while they still exist.
- Finviz bar times are Eastern; store times as UTC ISO strings like the rest of the app,
  show them in ET.
- Follow `.claude/rules/`: validate input at the boundary (pydantic), no `any`, TDD, README
  and docs in the same diff, an ADR in `docs/decisions/` for the bar-storage choice.
- The research-record draft (`2026-11-06-research-record-design.md`) also plans to store
  4 AM–8 PM minute bars, but it is not approved or built. The journal stores its own bars
  and must not depend on it. If both exist later, they can share storage.

## What the user decided

- Two kinds of entries: **trades** (real account) and **passes** (looked, didn't trade).
- Pass reasons are picked from a list; more than one can be picked; "Other" takes a note.
- Log from buttons on the Stock page's chart. No import.
- Fills: click a candle to fill time and price, **or** type price, time and shares. A trade
  can have any number of fills.
- Usually one entry and one exit, sometimes scaling in and out.
- Save bars (not screenshots) for every day the trade was open, including pre-market and
  after-hours, so the chart can be redrawn.
- Journal page shows: trades taken; P&L chart; average gain, average loss, average R:R;
  counts by country, industry and pattern; trade duration; average Sykes grade and
  average score traded.
- All six suggestions and the three "later" ones are in the first version (details below).

## Pass reasons (fixed list, grouped)

- **The app's read:** Low Sykes grade · Low score · No verdict / no clear edge · Leans short ·
  Bearish pattern too · Reward:risk too low (target capped) · Risk % too big (stop too far) ·
  Stop too tight
- **Timing:** Missed it · Too early (not confirmed) · Too late / extended · Would be chasing ·
  Bad time of day · Extended hours (thin, wide spread)
- **The stock:** Float too big · Low relative volume · Thin volume / wide spread ·
  Price outside my range · Already ran too far today · Resistance overhead ·
  Choppy, no clean level · Halt risk
- **News:** No catalyst · Weak or old news · Dilution risk (offering, warrants, shelf) ·
  Recent reverse split · Company red flags
- **Market:** Weak market / small caps cold · Sector not moving
- **Me:** Hit max daily loss · Hit daily goal, done for the day · Already in a position ·
  Pattern day trader limit / buying power · Not focused / tilted · Not in my playbook ·
  Other (note required)

Stored as stable keys (e.g. `low_sykes`), labelled in the UI. The list lives in one place in
the backend and is served to the frontend, so the two can't drift **(Claude's call)**.

## Mistake chips (trades only, optional, more than one)

Chased · Oversized · Moved my stop · Held a loser · Sold too early · Revenge trade · FOMO ·
Followed the plan. "Followed the plan" can't be combined with the others. Same storage
approach as pass reasons.

## Logging flow (Stock page)

Two buttons above the chart: **Log trade** and **Pass**. Shortcuts: `L` and `P` open them,
`Esc` closes; shortcuts are ignored while typing in an input.

**Values are as of the trade, not as of logging (user, 2026-11-09).** The user logs
sometimes during the trade, sometimes right after, sometimes at the end of the day, and
wants the setup and stock figures recorded as they were **when the trade was made** (a
pass: when the user passed). "Trade time" below means the first fill's time.

**Setup history (new).** Today an open setup record's score, state, verdict and Sykes grade
are overwritten on every rescan, and a setup that hits its stop drops out of the current
list. So the scanner also appends a history row whenever a setup's score, state, verdict or
Sykes grade changes: setup record id, scan time, and those values. This is the only change
to the scanner. History rows for setups older than 90 days may be pruned **(Claude's call)**.

**Linked setup.** Both panels offer a setup picker listing **all of that stock's setups
detected that trading day**, including ones that already hit their stop or target, plus
"No setup". Default: the setup selected in the Stock page's list when logging live;
otherwise the highest-scoring setup that was open at trade time. Each choice shows its
pattern, timeframe, and state at trade time.

On save, the app copies into the journal entry the setup's pattern, timeframe, planned
entry/stop/target/R:R, and its score, Sykes grade (letter and points), verdict and state
**from the last history row at or before the trade time** (falling back to the record's own
values if there is no history yet). It also keeps the `setup_records.id` link. Editing the
first fill's time re-copies them.

**Stock facts.**
- From the saved bars, as of trade time: price (the first fill), change % vs. the previous
  close, and volume so far that day. "Volume vs. average" is volume so far ÷ the quote's
  average daily volume, unscaled for time of day and labelled that way; Finviz's own
  relative volume is a live figure, so it can't be recovered for an earlier moment
  **(Claude's call)**.
- From the cached quote at save time (these don't move within a day): company, country,
  sector, industry, float, market cap.
- If the quote can't be fetched, those stay empty and the entry still saves.

**Pass panel:** reason chips (grouped as above), optional note, Save. Time and price are
taken from the moment of saving and the latest bar. Saving a pass also saves that day's bars
(so its chart can be reviewed) **(Claude's call)**.

**Log trade panel:**
- Direction: Long (default) / Short.
- Plan: stop and target, filled from the linked setup, editable. Required for R; if empty,
  R-based figures show "—".
- Fills table: side (Buy/Sell), time (ET), price, shares. Add a fill by:
  - clicking a candle while the panel is open: adds a fill with that bar's time and its
    close as the price; the next fill's side defaults to the opposite of the first (Buy then
    Sell for a long); price and time stay editable; or
  - typing all three in a new row.
  A price outside the clicked bar's low–high shows a warning, not an error.
- Shares are typed. Live preview: average entry, average exit, shares still held, money in,
  P&L ($ and R), position-size suggestion (see below).
- Mistake chips, fees (default $0), note.
- Save. A trade with shares still held saves as **open**; the user reopens it later from the
  journal or the Stock page to add exit fills.

**What counts as one trade (Claude's call).** A trade runs from the fill that opens a
position to the fill that brings it back to zero shares. Buying in again after that starts a
new trade (in-out-in on one ticker is two trades). Pressing Log trade on a stock that has an
open trade opens that trade to add fills, with a "Start a new trade instead" link.

**Validation (backend, pydantic):** ticker pattern as in `routes/stocks.py`; prices > 0;
shares positive whole numbers; fill times not in the future; at least one fill; the first fill
opens the position (Buy for long, Sell for short); the position can never go below zero or
flip sides; at most 50 fills per trade; notes ≤ 1,000 characters; reasons and mistakes must
be known keys **(limits are Claude's call)**.

## Saved bars

- What: 1-minute bars, 4:00 AM–8:00 PM ET, per **(ticker, trading day)**, for every day from
  a trade's first fill to its last fill (or today while open), and for a pass's day. 5-minute
  bars are built from the 1-minute ones when shown **(Claude's call)**.
- When: on saving or editing an entry, fetch `get_bars(ticker, "1m")` once and store every
  needed day that isn't stored complete yet.
- Completeness: a day saved before 8:00 PM ET is **partial**. A background job re-saves
  partial days after 8:00 PM ET, and saves new days for trades still open. Runs as part of
  the existing in-process feeder loop pattern (ADR 0001) or its own small loop **(builder's
  choice)**.
- Gone from Finviz: if a needed day is older than what Finviz returns, mark it **missing**.
  The entry still saves; the chart says "Bars for Oct 3 are no longer available from
  Finviz" for that day.
- Finviz errors: the entry saves; days stay unsaved and the background job retries. The UI
  says "Chart bars not saved yet, will retry".
- Storage: a new table keyed by (ticker, day), shared by every entry on that stock-day.

## Calculations (exact definitions shown on the page as tooltips)

- **Average entry / exit:** share-weighted average of opening / closing fills.
- **Money in:** the largest cost of the position held at any moment (shares × average entry
  at that point) **(Claude's call; total bought is shown in the trade detail too)**.
- **P&L ($):** closing proceeds − cost of the shares closed (average-cost method), minus fees.
  For shorts, the reverse. Open trades show realised P&L so far, marked "open".
- **Win / loss:** closed trade with P&L > 0 / < 0. Breakeven (= 0) counts as neither.
- **R:** P&L ÷ (|first entry price − plan stop| × largest shares held). No stop → no R.
- **Planned R:R:** |plan target − first entry| ÷ |first entry − plan stop|.
- **Duration:** first fill to last fill; open trades: to now.
- **Which period a trade belongs to (Claude's call).** Realised P&L is booked on the date
  of each closing fill, so the P&L chart, the period totals and the daily max-loss warning
  always agree, including for trades that scale out across days. Fees are booked with the
  final closing fill. Trade counts, win rate, averages and breakdowns count a trade in the
  period of its **last fill** (when it closed). Open trades are not in those stats; the
  summary shows "N open" separately. CSV export filters the same way.
- **Average Sykes grade:** average of the points (out of 14) of trades with a grade, shown
  as the letter for that average plus the number (e.g. "C · 8.6/14").

## Learning features

1. **Plan vs. actual.** Each trade shows planned stop/target vs. actual exits, and flags:
   "exited before target", "held past stop" (a price below the plan stop was reached while
   holding, from saved bars), "followed plan".
2. **Mistake chips** (above), with a breakdown: count and P&L per mistake.
3. **What happened after you sold.** From saved bars between the last fill and 8:00 PM ET
   that day: the best and worst price reached, shown in R (and $ per share without a stop):
   "kept going +1.4R after you sold" / "dropped 2.0R after you sold". Multi-day trades use
   the exit day only **(Claude's call)**. Summary: average R left on the table.
4. **P&L by time of day,** by the first fill's time: 4:00–9:30, 9:30–10, 10–11, 11–12,
   12–2, 2–4, 4–8 PM **(buckets Claude's call)**.
5. **Keyboard shortcuts** `L`, `P`, `Esc` (above).
6. **CSV export:** "Export" on the Journal tab downloads entries (one row per trade or pass)
   and fills (one row per fill) for the chosen period, as two files. Cells starting with
   `=`, `+`, `-` or `@` are escaped so spreadsheets don't run them as formulas.
7. **Position-size calculator.** Settings: risk per trade ($) and optional max position ($).
   Shown in the Log trade panel and on each setup card on the Stock page:
   "Size 625 sh ($1,150) to risk $50". Shares = floor(risk $ ÷ |entry − stop|), capped by max
   position ÷ entry. Hidden until a risk amount is set.
8. **Daily max-loss warning.** Setting: max daily loss ($). When today's realised P&L
   (all trades, after fees) reaches −limit, a red banner shows on Setups, Stock and in the
   Log trade panel: "Max daily loss reached (−$212 of −$200)". Warn only, never block.
   An amber note at 80% **(Claude's call)**.
9. **You vs. the system.** A table per pattern + timeframe: your trades, win rate, average R
   next to the system's track record for that pattern (`compute_track_record`), with the
   system's "not enough history yet" shown where it applies.

Settings for 7 and 8 live in the existing `app_meta` table through `user_settings.py`,
edited from a small settings panel on the Journal tab **(Claude's call)**.

## Scoring a pass (Claude's call)

The linked setup record's own outcome is judged from when the scanner first saw the setup,
not from when the user passed, so it can't answer "was this pass right". Passes are scored
from the journal's saved bars instead, starting at the pass time:

- Stop and target: the linked setup's stop and target as copied at pass time.
- Simulated entry: if price was already past the setup's entry when the user passed (common
  for "Missed it", "Too late", "Would be chasing"), the entry is the pass price; otherwise
  the trade fills only if price later reaches the setup's entry.
- Then the existing resolver rules apply (stop wins when one bar touches both), up to
  8:00 PM ET that day for 1m/5m setups. Daily-timeframe setups are scored over the bars
  saved for the pass day only and usually show "undecided" **(Claude's call)**.
- Buckets: would have hit target (+R) · would have stopped (−1R) · never filled ·
  undecided by 8 PM. Passes without a linked setup (or without a stop) are counted by
  reason but not scored.

This is a small scoring module with its own tests, reusing the resolver's bar-walking rules.

## Journal tab

New tab "Journal", placed before "Track record" **(Claude's call)**.

- **Period filter** at the top: Today · This week · This month · All time. Everything follows it.
- **Daily max-loss banner** when relevant.
- **Summary row:** net P&L, trades, win rate, average gain, average loss, largest win,
  largest loss, average planned R:R vs. average R made, average duration, average Sykes
  grade, average score, passes.
- **P&L chart:** cumulative P&L line, with each closed trade's P&L as a bar beneath, by
  close time.
- **Breakdowns** (each row: count, P&L): country, industry, pattern, mistakes, time of day,
  duration (under 5 min, 5–30 min, 30 min to close, multi-day), and passes by reason with
  what the passed setups would have done (see "Scoring a pass").
- **You vs. the system** table (feature 9).
- **List:** every trade and pass, newest first. Trade row: ticker, date, setup, direction,
  average entry/exit, shares, money in, P&L ($, R), duration, status (open / closed).
  Pass row: ticker, date, setup, reasons. Filters: trades / passes / both.
- **Detail** (click a row): the saved chart (1m / 5m) with buy markers below bars and sell
  markers above, sized by shares, labelled "B 500 @ 1.84"; plan stop/target lines; plan vs.
  actual flags; what happened after; fills table; edit and delete (delete asks to confirm);
  "Save as image".
- The Stock page also marks that stock's logged fills on its live chart **(Claude's call)**.

## API (shape; names are the builder's choice)

- Journal entries: create, list (period, kind), get one, update, delete.
- Reasons and mistakes lists.
- Summary for a period.
- Saved bars for an entry.
- CSV export (entries, fills).
- Settings: risk per trade, max position, max daily loss.

## Left to the builder

- Table and column names, route paths, component split.
- Whether the bar-saving job joins the feeder loop or runs alongside it.
- Exact layout and styling within the current look.
- The ADR wording for storing bars per stock-day.
