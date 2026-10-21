# Phase 2 Milestone 3 — Track Record, Candlesticks, Continuation and Reversal Patterns

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show which patterns actually work on the user's stocks (Track record view), let
that history and candlestick confirmation feed each setup's score, and add the
continuation and reversal patterns.

**Architecture:** Track-record statistics are a pure aggregation over `setup_records`
(`app/setups/track_record.py`) exposed by one route and one view. Ranking gains two parts
(`track_record`, `candles`) computed by the scanner. New detectors use the existing registry
and `find_swings`.

**Tech Stack:** unchanged; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md`
(section 3 continuation/reversal/candlestick tables, 5 "track record" ranking, 5b outcomes,
7 Track record view).

## Global Constraints

- Same constraints as milestones 2a/2b (pure detectors, direction-aware, shorts as
  warnings while hidden, every commit gated on the test commands themselves — no pipes).
- Track-record numbers count only trades someone could have taken: outcomes `target`,
  `stop`, and `expired` **with a fill** (`max_favorable_r` not null). `not_tracked`,
  `unresolved`, `open` and unfilled `expired` are excluded and shown as separate counts.
- `MIN_TRADES_FOR_TRACK_RECORD = 30` per pattern × timeframe before history affects a score.

## Review Focus

1. Win rate and average R must ignore setups that were never trades (Task 1
   `test_unfilled_and_untracked_setups_are_not_trades`).
2. A pattern with fewer than 30 trades must not move scores (Task 3
   `test_track_record_ignored_below_thirty_trades`).
3. New detectors must return `[]` on short or flat series (each detector task).
4. Candlestick signals far from the setup's levels must not change its score (Task 4
   `test_candle_away_from_key_levels_is_ignored`).

---

### Task 1: Track-record statistics

**Files:** create `backend/app/setups/track_record.py`; test `backend/tests/test_track_record.py`.

- `FloatBucket = Literal["under_5m", "5m_to_10m", "10m_to_20m", "20m_to_50m", "over_50m", "unknown"]`;
  `def float_bucket(float_millions: float | None) -> FloatBucket` (boundaries 5/10/20/50, lower bound inclusive).
- `@dataclass(frozen=True) class PatternStats: pattern, timeframe, trades, wins, losses, expired_after_fill, win_rate: float | None, average_r: float | None, average_max_favorable_r: float | None, not_trades: int, still_open: int`.
- R per trade: `target` → the record's `available_reward_risk`; `stop` → −1; filled
  `expired` → 0 (exit price isn't recorded; documented in the module).
- `def compute_track_record(conn, *, pattern=None, timeframe=None, float_bucket=None, session=None) -> list[PatternStats]`
  grouped by (pattern, timeframe), sorted by trades desc.
- `def stats_for(conn, pattern, timeframe) -> PatternStats | None`.
- Tests: wins/losses/R averages from fixture records; `test_unfilled_and_untracked_setups_are_not_trades`;
  filters by float bucket and session; float bucket boundaries.

### Task 2: Track record API and view

**Files:** `backend/app/routes/track_record.py`, `schemas.py`, `main.py`; frontend
`api/trackRecord.ts`, `components/TrackRecordView.tsx` (+ test), `App.tsx`.

- `GET /api/track-record?pattern=&timeframe=&float_bucket=&session=` → `{rows: PatternStatsOut[], min_trades: 30}`;
  query params validated (Literal types; pattern must match `^[a-z_]{1,40}$`).
- New tab "Track record": filters (timeframe, float bucket, session) and a table: pattern,
  timeframe, trades, win rate, average R, average best excursion (MFE), not-trades and open
  counts. Rows under 30 trades are shown muted with "not enough history yet". Empty state
  explains outcomes collect as setups resolve (intraday by 8 PM ET, daily after 20 sessions).
- Tests: route filters and validation; view renders, filters, muted rows, empty state.

### Task 3: Track record in the ranking

**Files:** `patterns/ranking.py`, `scanning/scanner.py`, `routes/setups.py`, `schemas.py`, frontend `SetupsView.tsx`.

- `score_setup(..., track_record: PatternStats | None = None)`; part `track_record` (points):
  `TRACK_RECORD_POINTS = 15`; when `trades ≥ 30`, `clamp(average_r, -1, 1) × 15`; otherwise 0.
  Total still clamped 0–100.
- Scanner looks up `stats_for(pattern, timeframe)` once per pair per scan.
- `SetupOut.track_record: {trades, win_rate, average_r} | null`; Setups score breakdown
  shows "Track record: 42 trades, 48% wins, +0.3R" or "not enough history (12 trades)".
- Tests: `test_track_record_ignored_below_thirty_trades`, positive/negative history moves the
  score, API includes it, UI shows both texts.

### Task 4: Candlestick confirmation

**Files:** create `backend/app/patterns/candles.py`; modify `ranking.py`, `scanner.py`; test `test_candles.py`.

- `CandleSignal = Literal["bullish_engulfing", "bearish_engulfing", "hammer", "shooting_star", "morning_star", "evening_star", "doji"]`;
  `def detect_candle_signals(bars) -> list[tuple[CandleSignal, Bar]]` on the last 1–3 bars
  (standard definitions; body/wick ratios as named constants: hammer lower wick ≥ 2× body and
  upper wick ≤ body; doji body ≤ 10% of range; engulfing body covers prior body).
- Bullish signals: engulfing, hammer, morning star; bearish: engulfing, shooting star,
  evening star; doji neutral (no score change, listed).
- Key level match: a bullish signal whose bar low is within `KEY_LEVEL_TOLERANCE = 1%` of a
  long setup's stop or entry adds `CANDLE_POINTS = 5`; a bearish signal at a long setup's
  entry subtracts 5. Mirrored for shorts. Part `candles`.
- Tests: each signal shape, `test_candle_away_from_key_levels_is_ignored`, score effect.

### Task 5: Pennants, symmetrical triangles, wedges

**Files:** `patterns/detectors/converging.py` (+ registry); test `test_converging_detectors.py`.

- Shared: in the last `CONVERGING_LOOKBACK = 40` bars, swing highs and lows (≥ 2 each).
- Bull/bear pennant (`bull_pennant`/`bear_pennant`): flag-style pole (reuse the flag pole
  thresholds) followed by a converging consolidation (lower highs and higher lows). Entry =
  latest swing high (bull), stop = latest swing low.
- Symmetrical triangle (`symmetrical_triangle_up`/`_down`): lower highs and higher lows
  with no pole requirement; direction = the side price is within 2% of or has just closed
  through; entry = that edge's latest swing, stop = the other edge's latest swing.
- Falling wedge (bull) / rising wedge (bear): highs and lows both falling (rising), lows
  falling slower than highs (converging); entry = latest swing high (low for rising), stop
  = latest swing low (high).
- Tests per pattern incl. near-misses and flat/short series.

### Task 6: Ranges and cups

**Files:** `patterns/detectors/ranges_cups.py` (+ registry); tests.

- Range (`range_breakout`/`range_breakdown`): last 20 bars span ≤ `{1m: 3%, 5m: 6%, daily: 15%}`
  with ≥ 2 swing highs near the top and ≥ 2 swing lows near the bottom (within 15% of the
  range); price within 2% of / just through an edge. Entry = edge; stop = opposite edge.
- Cup and handle (`cup_and_handle`, long) / inverted (`inverted_cup_and_handle`, short):
  rims (window start and right rim) within 3% of each other; cup low in the middle half of
  the cup, 10–50% below the rims; handle = last 3–10 bars drifting down no more than a third
  of the cup depth. Entry = right rim; stop = handle low.
- Tests per pattern incl. near-misses.

### Task 7: Reversal patterns

**Files:** `patterns/detectors/reversals.py` (+ registry, timeframes 5m and daily per spec); tests.

- Head and shoulders (short) / inverse (long): three consecutive swing highs (lows), middle
  the most extreme, shoulders within 3% of each other; neckline = the higher (lower) of the
  two swing lows (highs) between them. Relevant when within 3% of / just through the
  neckline. Entry = neckline; stop = right shoulder.
- Triple top/bottom: three tests within 2% with two necklines between; entry = the
  outermost neckline; stop = beyond the tests (like doubles).
- Rounding bottom/top: window of 30 bars whose lowest close is in the middle third and both
  ends ≥ `{5m: 3%, daily: 10%}` above it, with closes declining then rising (at most 25% of
  steps against the trend in each half). Entry = the higher end; stop = the bottom.
- Tests per pattern.

### Task 8: Names, docs, live check

- Frontend `PATTERN_NAMES` for all new patterns; README pattern list, Track record section,
  how history and candles move scores.
- Live: branch stack on a DB copy; screenshot Track record, Setups (score details), Stock.
