# Phase 2 Milestone 2a — Bars, First Patterns, Setups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scan the active watchlist on 1m/5m/daily Finviz bars, detect the first set of
patterns, turn each long match into an entry/stop/3R plan capped by daily resistance, rank
them, record every match for outcome tracking, and show it all in a Setups tab and a Stock
tab with a candle chart.

**Architecture:** `finviz_client` gains bar and snapshot fetches. Pure modules under
`app/patterns/` (indicators, daily levels, detectors, trade plan, ranking) take bars in and
return values; `app/setups/` stores matches and resolves outcomes; `app/scanning/` chooses
which tickers to scan, loads bars through a SQLite cache, runs everything, and is called
by routes and by the existing feeder loop. The frontend adds Setups and Stock views; the
Stock view draws candles with TradingView lightweight-charts.

**Tech Stack:** Python 3.12, FastAPI, pandas, SQLite, pytest + responses; React 18 + TS +
Vite, Vitest + Testing Library. New frontend dependency: `lightweight-charts@^4.2.0`
(Apache-2.0, ~45 KB gzipped; v4 API — `addCandlestickSeries`, `createPriceLine`).

**Spec:** `docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md`
(sections 3, 4, 5, 5b, 6, 7, Architecture, Data model, API, Errors, Testing).

**Scope split (ruling):** the spec's milestone 2 is split into 2a (this plan) and 2b
(triangles, double top/bottom, ABCD, micro pullback, first pullback, EMAs and the
per-stock verdict).
2a delivers a complete, usable pipeline; 2b adds detectors to the same interface plus the
verdict.

## Global Constraints

- Follow `.claude/rules/*.md`. Pattern code has no I/O: bars in, matches/plans out.
- All Finviz requests go through `finviz_client` and its pacer (≤ 1 request/second).
- Detection is rule-based; UI copy says "detected", never "will".
- Every setup shows its stop and its **available** reward:risk; never claim 3:1 when a
  daily level caps it lower.
- Direction-aware everywhere: `direction: Literal["long", "short"]`. Short matches are
  shown as warnings unless the `show_short_setups` setting is on (default **off**).
- Never suggest a short trade while `show_short_setups` is off.
- Sessions (America/New_York): pre-market 04:00–09:29, regular 09:30–15:59, after-hours
  16:00–19:59. VWAP anchored at 04:00 ET. Opening range 09:30–09:34. Previous close from
  daily bars.
- `TARGET_R = 3`. Partial-profit levels at 1R and 2R.
- Bar cache: 1m valid 60 s, 5m valid 300 s, daily valid until the next 16:00 ET close.
- Active tickers: in a current screen result, or rel vol ≥ 1.5, or |change| ≥ 5%, or
  |after-hours change| ≥ 5%. Cap **40** per scan, most active first.
- Outcome: target or stop, whichever is hit first after entry; both in one bar → `stop`.
  Never triggered by expiry → `expired`. Intraday setups expire at 20:00 ET that day;
  daily setups after 20 sessions. Bars no longer available → `unresolved`.
- Timeframes: `Interval = Literal["1m", "5m", "daily"]`, ordered 1m < 5m < daily.

## Review Focus

1. A ticker with no bars for today (not traded yet, halted, or Finviz returns only older
   bars) must scan without error and simply produce no intraday matches (Task 3
   `test_session_levels_empty_when_no_bars_today`; Task 5
   `test_level_break_detectors_return_nothing_without_session`).
2. A match whose stop is at or beyond its entry (zero or negative risk) must never become
   a setup or divide by zero (Task 7 `test_build_trade_plan_rejects_non_positive_risk`).
3. After-hours bars stamped `19:59 PM` and bars on DST-change days must land on the right
   Eastern date and session (Task 1 `test_parse_intraday_timestamp_after_hours`; Task 3
   `test_vwap_resets_each_eastern_day`).
4. One ticker failing mid-scan (auth, 429, bad CSV) must not stop the others; the scan
   result lists it (Task 10 `test_run_scan_continues_after_ticker_failure`).
5. A manual scan overlapping the scheduled one, or the same pattern seen on consecutive
   scans, must not create duplicate records (Task 9
   `test_record_match_twice_updates_existing_record`).

---

## File Structure

Backend (`backend/app/`):
- Modify `finviz_client.py`: `Bar`, `get_bars`, `get_snapshots`; `_fetch_export_csv` takes a URL.
- Create `bars/__init__.py`, `bars/cache.py` (SQLite bar cache + freshness), `bars/loader.py` (`load_bars`).
- Create `patterns/__init__.py`, `patterns/types.py` (shared dataclasses), `patterns/indicators.py`,
  `patterns/levels.py`, `patterns/detectors/__init__.py` (registry + `run_detectors`),
  `patterns/detectors/level_breaks.py`, `patterns/detectors/flags.py`,
  `patterns/detectors/flat_levels.py`, `patterns/trade_plan.py`, `patterns/ranking.py`.
- Create `setups/__init__.py`, `setups/store.py`, `setups/resolver.py`.
- Create `scanning/__init__.py`, `scanning/active.py`, `scanning/scanner.py`, `scanning/snapshots.py`.
- Create `routes/bars.py`, `routes/setups.py`, `routes/settings.py`; modify `routes/watchlist.py`,
  `schemas.py`, `main.py`, `db.py` (new tables), `watchlist/scheduler.py` (scan after feeder).
- Modify `scripts/finviz_sanity_check.py` (`--bars`).

Frontend (`frontend/src/`):
- Create `api/setups.ts`, `api/bars.ts`, `api/settings.ts`; modify `api/watchlist.ts`.
- Create `components/SetupsView.tsx`, `components/StockView.tsx`, `components/CandleChart.tsx`,
  `chartTime.ts`; delete `components/LookupView.tsx` (Stock view replaces it); modify `App.tsx`,
  `components/WatchlistView.tsx`, `components/ScreenResultsTable.tsx`, `styles.css`.

Docs: `README.md`, `docs/decisions/0003-lightweight-charts.md`,
`docs/decisions/0004-scan-only-active-tickers.md`.

---

### Task 1: Finviz bars and snapshots

**Files:** Modify `backend/app/finviz_client.py`; Test `backend/tests/test_finviz_bars.py`

**Interfaces:**
- Produces:
  - `Interval = Literal["1m", "5m", "daily"]`; `BAR_PERIOD_CODES = {"1m": "i1", "5m": "i5", "daily": "d"}`.
  - `@dataclass(frozen=True) class Bar: time: datetime` (tz-aware, America/New_York; daily bars at 00:00 ET of their date), `open: float, high: float, low: float, close: float, volume: int`.
  - `FINVIZ_BARS_URL = "https://elite.finviz.com/quote_export.ashx"`.
  - `def parse_bar_time(raw: str, interval: Interval) -> datetime`.
  - `def get_bars(ticker: str, interval: Interval) -> list[Bar]` — oldest first; header-only CSV → `[]`.
  - `def get_snapshots(tickers: list[str]) -> list[ScreenRow]` — `v=152&c=SCREEN_COLUMN_IDS&t=<comma list>`, batches of `SNAPSHOT_BATCH_SIZE = 100`, empty input → `[]` with no request.
  - `_fetch_export_csv(url: str, params: dict[str, str], operation: str) -> str` (existing callers pass `FINVIZ_EXPORT_URL`).

- [ ] **Step 1: Write failing tests**

```python
def test_parse_intraday_timestamp_after_hours():
    # Finviz writes a 24-hour clock with a redundant AM/PM suffix.
    parsed = parse_bar_time("10/20/2026 19:59 PM", "1m")
    assert parsed == datetime(2026, 10, 20, 19, 59, tzinfo=EASTERN)

def test_parse_intraday_timestamp_morning():  # "10/06/2026 04:00 AM" -> 04:00 ET
def test_parse_daily_date():  # "10/20/2026" -> datetime(2026, 10, 20, 0, 0, tzinfo=EASTERN)
def test_get_bars_parses_rows_oldest_first():  # 2-row CSV "Date,Open,High,Low,Close,Volume"
def test_get_bars_sends_period_code():  # query t=HOST, p=i5, auth
def test_get_bars_returns_empty_for_header_only_csv():
def test_get_bars_raises_unavailable_on_html_page():  # match "unexpected response format"
def test_get_snapshots_batches_tickers():  # 150 tickers -> 2 requests (100 + 50) with t= lists
def test_get_snapshots_makes_no_request_for_empty_list():
```

- [ ] **Step 2: Run** `cd backend && .venv/bin/python -m pytest tests/test_finviz_bars.py -q` → FAIL (ImportError).
- [ ] **Step 3: Implement.** Strip a trailing ` AM`/` PM` before `strptime("%m/%d/%Y %H:%M")`. `_read_csv_as_strings` requires a `Ticker` column today; give it a `required_column` parameter (`"Date"` for bars). Map a non-numeric bar cell to `FinvizUnavailableError(..., UNEXPECTED_FORMAT)`. Import `EASTERN` from `app.watchlist.store`.
- [ ] **Step 4: Run** full backend suite → PASS.
- [ ] **Step 5: Commit** `feat(finviz): fetch price bars and batched ticker snapshots`

---

### Task 2: Bar cache and loader

**Files:** Create `backend/app/bars/__init__.py`, `bars/cache.py`, `bars/loader.py`; modify `backend/app/db.py`; Test `backend/tests/test_bar_cache.py`

**Interfaces:**
- Consumes: `Bar`, `Interval`, `get_bars` (Task 1).
- Produces:
  - Table `bar_cache(ticker TEXT, interval TEXT, fetched_at TEXT, bars TEXT /* JSON */, PRIMARY KEY (ticker, interval))`.
  - `@dataclass(frozen=True) class BarSeries: bars: list[Bar]; fetched_at: datetime`.
  - `def is_cache_fresh(interval: Interval, fetched_at: datetime, now: datetime) -> bool` — 1m: < 60 s old; 5m: < 300 s; daily: no 16:00 ET close has passed between `fetched_at` and `now`.
  - `def read_cached_bars(conn, ticker, interval) -> BarSeries | None`; `def write_cached_bars(conn, ticker, interval, series: BarSeries) -> None`.
  - `def load_bars(conn, ticker: str, interval: Interval, now: datetime, fetch_bars_fn: Callable[[str, Interval], list[Bar]]) -> BarSeries` — cache hit if fresh, else fetch, store, return.

- [ ] **Step 1: Write failing tests**

```python
def test_one_minute_bars_fresh_for_60_seconds(): # 59s True, 61s False
def test_five_minute_bars_fresh_for_300_seconds():
def test_daily_bars_stale_after_the_close():
    # fetched 15:30 ET, now 16:05 ET same day -> False; fetched 16:10, now 23:00 -> True;
    # fetched Fri 17:00, now Mon 10:00 -> True (no close passed on the weekend)
    # fetched Fri 17:00, now Mon 16:01 -> False
def test_load_bars_uses_fresh_cache(db_conn):  # fetch_fn not called on second load within 60s
def test_load_bars_refetches_stale_cache(db_conn):
def test_cached_bars_round_trip_with_timezones(db_conn):  # Bar.time tz preserved
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (store bar times as ISO strings with offset). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bars): cache Finviz bars in SQLite with per-interval freshness`

---

### Task 3: Indicators and session levels

**Files:** Create `backend/app/patterns/__init__.py`, `patterns/types.py`, `patterns/indicators.py`; Test `backend/tests/test_indicators.py`

**Interfaces:**
- Consumes: `Bar` (Task 1).
- Produces (`types.py`):
  - `Direction = Literal["long", "short"]`; `SetupState = Literal["forming", "triggered", "extended", "invalidated"]`; `TIMEFRAME_ORDER = {"1m": 0, "5m": 1, "daily": 2}`.
  - `@dataclass(frozen=True) class SessionLevels: premarket_high, premarket_low, day_high, day_low, opening_range_high, opening_range_low, previous_close` — each `float | None`.
- Produces (`indicators.py`):
  - `def session_vwap(bars: list[Bar]) -> list[float | None]` — per bar, cumulative Σ(typical price × volume) / Σ volume from the first bar of that bar's Eastern date at or after 04:00; resets each Eastern date; `None` before 04:00 or while volume is 0. Typical price = (high + low + close) / 3.
  - `def session_levels(intraday_bars: list[Bar], daily_bars: list[Bar], today: date) -> SessionLevels` — only bars on Eastern date `today`; pre-market 04:00–09:29, regular 09:30–15:59, opening range 09:30–09:34; `previous_close` = close of the last daily bar dated before `today`.

- [ ] **Step 1: Write failing tests**

```python
def test_vwap_weights_by_volume():
def test_vwap_resets_each_eastern_day():  # bars 19:59 Oct 20 and 04:00 Oct 21 -> second VWAP == its own typical price
def test_vwap_ignores_bars_before_four_am():
def test_session_levels_split_premarket_and_regular():
def test_session_levels_opening_range_is_first_five_minutes():
def test_session_levels_previous_close_from_daily_bars():
def test_session_levels_empty_when_no_bars_today():  # all intraday fields None, previous_close still set
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): add session VWAP and session levels`

---

### Task 4: Daily support/resistance levels

**Files:** Create `backend/app/patterns/levels.py`; Test `backend/tests/test_levels.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class PriceLevel: price: float; touches: int`.
  - Constants: `LEVEL_LOOKBACK_BARS = 504` (≈2 years), `SWING_WINDOW = 5`, `MERGE_TOLERANCE_PERCENT = 1.5`, `MIN_TOUCHES = 2`.
  - `def find_daily_levels(daily_bars: list[Bar]) -> list[PriceLevel]` — sorted by price ascending.
  - `def nearest_level_above(levels, price: float) -> PriceLevel | None` (strictly above); `def nearest_level_below(levels, price: float) -> PriceLevel | None` (strictly below).
- Algorithm (stand-in for the user's hand-drawn lines):
  1. Use the last `LEVEL_LOOKBACK_BARS` daily bars.
  2. A swing high is a bar whose high is ≥ the highs of the `SWING_WINDOW` bars on each side; a swing low likewise with lows ≤. Bars without a full window on both sides are skipped.
  3. Sort all swing prices; walk upward, adding a price to the current cluster when it is within `MERGE_TOLERANCE_PERCENT` of the cluster's mean, else starting a new cluster.
  4. Each cluster with ≥ `MIN_TOUCHES` prices becomes a level at the cluster mean, `touches` = cluster size.

- [ ] **Step 1: Write failing tests**

```python
def test_two_matching_swing_highs_make_a_level():  # highs 10.0 and 10.1 with 5-bar shoulders -> one level ~10.05, touches 2
def test_single_swing_is_not_a_level():
def test_far_apart_swings_stay_separate():  # 10.0/10.1 and 12.0/12.1 -> two levels
def test_only_last_504_bars_are_used():
def test_nearest_level_above_and_below_are_strict():
def test_no_levels_for_short_history():  # < 11 bars -> []
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): find daily support and resistance levels`

---

### Task 5: Detector interface and level-break detectors

**Files:** Create `backend/app/patterns/detectors/__init__.py`, `detectors/level_breaks.py`; extend `patterns/types.py`; Test `backend/tests/test_level_break_detectors.py`

**Interfaces:**
- Produces (`types.py`):
  - `@dataclass(frozen=True) class PatternMatch: pattern: str; direction: Direction; timeframe: Interval; entry: float; stop: float; detected_at: datetime; quality: float; quality_parts: dict[str, float]; key_points: list[tuple[datetime, float]]`.
  - `@dataclass(frozen=True) class DetectorContext: timeframe: Interval; daily_levels: list[PriceLevel]; session: SessionLevels | None; vwap: list[float | None] | None` (`session`/`vwap` are `None` for daily bars; `vwap` aligned to the bar list).
- Produces (`detectors/__init__.py`):
  - `Detector = Callable[[list[Bar], DetectorContext], list[PatternMatch]]`.
  - `DETECTORS: list[tuple[Detector, frozenset[Interval]]]` — the registry; Tasks 5–6 append.
  - `def run_detectors(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]` — runs every detector registered for `context.timeframe`.
- Produces (`level_breaks.py`), intraday only (`1m`, `5m`). Pattern names (used as-is in DB and UI keys):
  `high_of_day_break`/`low_of_day_break`, `premarket_high_break`/`premarket_low_break`,
  `opening_range_breakout`/`opening_range_breakdown`, `red_to_green`/`green_to_red`,
  `vwap_reclaim`/`vwap_rejection`.
- Shared rule `def match_level_break(bars, level: float | None, direction, pattern, timeframe) -> PatternMatch | None` with `RECENT_BARS = 3`, `NEAR_LEVEL_PERCENT = 2.0`, `STOP_LOOKBACK_BARS = 5`:
  - Relevant when the last close is within `NEAR_LEVEL_PERCENT` short of the level (forming) or one of the last `RECENT_BARS` bars closed through it (just broke). Otherwise `None`.
  - `entry = level`; long `stop` = lowest low of the last `STOP_LOOKBACK_BARS` bars (short: highest high). `None` if stop isn't on the losing side of entry.
  - `quality_parts = {"proximity": 1 - distance/NEAR_LEVEL_PERCENT (1.0 once broken), "volume": min(last bar volume / average volume of the prior 20 bars / 2, 1)}`; `quality` = mean.
- Level per pattern: high/low of day = regular-session high/low **excluding the last `RECENT_BARS` bars** (otherwise the current bar is always the high); only during regular hours. Pre-market high/low: only once the regular session has started. Opening range: from 09:35 on. Previous close: any session. VWAP: long when ≥ 3 consecutive closes below VWAP are followed by the last close above it (`entry` = last bar high); short mirrored.

- [ ] **Step 1: Write failing tests** (fixture helper builds 1m bars from `(time, o, h, l, c, v)` tuples)

```python
def test_high_of_day_break_detects_close_through_prior_high():
def test_high_of_day_break_forming_just_below_level():
def test_high_of_day_break_ignored_when_far_below():  # 5% below -> []
def test_premarket_high_break_not_detected_before_open():
def test_opening_range_breakout_needs_range_complete():  # at 09:33 -> []
def test_red_to_green_uses_previous_close():
def test_vwap_reclaim_after_three_closes_below():
def test_short_patterns_mirror_long():  # low_of_day_break direction == "short", stop above entry
def test_level_break_detectors_return_nothing_without_session():  # session=None or empty bars -> []
def test_run_detectors_only_runs_detectors_for_timeframe():  # daily context -> no level-break matches
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): add detector registry and momentum level-break detectors`

---

### Task 6: Flag and flat-level detectors

**Files:** Create `backend/app/patterns/detectors/flags.py`, `detectors/flat_levels.py`; Test `backend/tests/test_flag_detectors.py`, `backend/tests/test_flat_level_detectors.py`

**Interfaces:**
- Consumes: Task 5 types and registry. All four run on `1m`, `5m`, `daily`.
- Produces patterns `bull_flag`/`bear_flag` and `flat_top_breakout`/`flat_bottom_breakdown`.
- Flag rules (per-timeframe constants in a dict keyed by `Interval`):
  `POLE_MIN_MOVE_PERCENT = {"1m": 3.0, "5m": 5.0, "daily": 15.0}`, `POLE_MAX_BARS = {"1m": 10, "5m": 8, "daily": 6}`, `FLAG_BARS = (3, 12)` (min, max), `MAX_RETRACE = 0.5`.
  - The flag is the last 3–12 bars; the pole is the up-move (bull) ending at the bar before the flag, starting at the lowest low within `POLE_MAX_BARS` before that.
  - Bull: pole gain ≥ threshold; flag's lowest low retraces ≤ `MAX_RETRACE` of the pole; flag's highest high ≤ pole top. `entry` = flag's highest high, `stop` = flag's lowest low.
  - `quality_parts = {"pole_strength": min(gain/threshold/2, 1), "shallow_retrace": 1 - retrace/MAX_RETRACE, "volume_contraction": 1.0 if flag avg volume < pole avg volume else 0.0}`.
  - Bear mirrored. Try flag lengths from 3 up to 12 and return the highest-quality match only.
- Flat level rules: `FLAT_LOOKBACK_BARS = 30`, `FLAT_TOLERANCE_PERCENT = 0.5`, `MIN_FLAT_TOUCHES = 3`.
  - Flat top: ≥ 3 highs in the lookback within 0.5% of the lookback's highest high, and the last close below or within 2% above that level. `entry` = the level; `stop` = lowest low since the first touch.
  - `quality_parts = {"touches": min(touches/5, 1), "tightness": 1 - (high spread %)/FLAT_TOLERANCE_PERCENT}`. Bottom mirrored.

- [ ] **Step 1: Write failing tests**

```python
def test_bull_flag_detected_after_pole_and_tight_consolidation():  # 1m pole +6% in 5 bars, 5-bar flag retracing 30%
def test_flag_rejected_when_retrace_too_deep():  # 60% retrace -> []
def test_flag_rejected_when_pole_too_small():  # +2% on 1m -> []
def test_flag_thresholds_differ_by_timeframe():  # +6% pole matches on 1m, not on daily
def test_bear_flag_mirrors_bull_flag():
def test_flat_top_needs_three_touches():  # 2 touches -> [], 3 touches -> match
def test_flat_top_entry_is_the_level_and_stop_below():
def test_flat_bottom_breakdown_is_short():
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): add flag and flat-level detectors on all timeframes`

---

### Task 7: Trade plan and setup state

**Files:** Create `backend/app/patterns/trade_plan.py`; Test `backend/tests/test_trade_plan.py`

**Interfaces:**
- Consumes: `PatternMatch`, `PriceLevel`, `nearest_level_above/below`, `Bar`.
- Produces:
  - `TARGET_R = 3.0`.
  - `@dataclass(frozen=True) class TradePlan: direction: Direction; entry: float; stop: float; risk_per_share: float; risk_percent: float; target_3r: float; capped_target: float; available_reward_risk: float; blocking_level: float | None; partial_1r: float; partial_2r: float; trailing_stop: float | None`.
  - `def build_trade_plan(match: PatternMatch, daily_levels: list[PriceLevel], recent_bars: list[Bar]) -> TradePlan | None` — `None` when risk ≤ 0. Long: blocking level = nearest daily level strictly above entry and strictly below `target_3r`; then `capped_target` = that level and `available_reward_risk = (level - entry) / risk`, else `target_3r` and `3.0`. Short mirrored with levels below. `risk_percent = risk / entry * 100`. `trailing_stop` (long) = the low of the most recent bar in `recent_bars` whose low is below the lows of the 2 bars on each side; short = matching swing high; `None` if none.
  - `def classify_state(plan: TradePlan, last_price: float) -> SetupState` — long: `invalidated` if price ≤ stop; `forming` if < entry; `triggered` if < entry + 1R; else `extended`. Short mirrored.

- [ ] **Step 1: Write failing tests**

```python
def test_long_plan_uses_three_r_target_when_path_is_clear():
    # entry 2.00, stop 1.90 -> risk 0.10, target 2.30, available 3.0, risk_percent 5.0
def test_long_plan_capped_by_daily_resistance():
    # level at 2.15 -> capped_target 2.15, available_reward_risk 1.5, blocking_level 2.15
def test_level_exactly_at_entry_does_not_cap():
def test_short_plan_capped_by_support_below():
def test_partial_levels_at_one_and_two_r():  # 2.10, 2.20
def test_trailing_stop_is_most_recent_swing_low():
def test_build_trade_plan_rejects_non_positive_risk():  # stop == entry and stop above entry (long) -> None
def test_classify_state_long_boundaries():  # 1.90 invalidated, 1.99 forming, 2.00 triggered, 2.10 extended
def test_classify_state_short_mirrors():
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): build entry/stop/target plans capped by daily levels`

---

### Task 8: Ranking

**Files:** Create `backend/app/patterns/ranking.py`; Test `backend/tests/test_ranking.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class ScoreBreakdown: total: float; parts: dict[str, float]` — `total` 0–100.
  - `WEIGHTS = {"reward_risk": 0.40, "quality": 0.25, "volume": 0.15, "freshness": 0.10, "timeframe_agreement": 0.10}`; `CONFLICT_PENALTY = 0.20`.
  - `def score_setup(match: PatternMatch, plan: TradePlan, state: SetupState, relative_volume: float | None, other_matches: list[PatternMatch]) -> ScoreBreakdown`:
    - `reward_risk = min(plan.available_reward_risk, 3) / 3`; `quality = match.quality`; `volume = min((relative_volume or 0) / 3, 1)`; `freshness` = 1.0 forming/triggered, 0.3 extended; `timeframe_agreement` = 1.0 if another same-direction match exists on a different timeframe, else 0.0.
    - `conflict` = `-CONFLICT_PENALTY` when an opposite-direction match exists on the same or a higher timeframe, else 0.
    - `total = clamp(Σ weight × part + conflict, 0, 1) × 100`, rounded to 1 decimal; `parts` holds each weighted contribution plus `conflict`.

- [ ] **Step 1: Write failing tests**

```python
def test_reward_risk_dominates_score():  # 3R vs 1R plan, all else equal -> higher total
def test_no_extra_credit_above_three_r():
def test_extended_setups_rank_below_fresh_ones():
def test_agreement_on_another_timeframe_adds_bonus():
def test_opposite_pattern_on_higher_timeframe_penalises():
def test_opposite_pattern_on_lower_timeframe_does_not_penalise():
def test_parts_sum_to_total():
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): rank setups with a visible score breakdown`

---

### Task 9: Setup records and outcome resolver

**Files:** Create `backend/app/setups/__init__.py`, `setups/store.py`, `setups/resolver.py`; modify `backend/app/db.py`; Test `backend/tests/test_setup_store.py`, `backend/tests/test_resolver.py`

**Interfaces:**
- Consumes: `PatternMatch`, `TradePlan`, `ScoreBreakdown`, `SetupState`, `Bar`.
- Produces:
  - Table `setup_records(id INTEGER PK, ticker, pattern, direction, timeframe, entry REAL, stop REAL, capped_target REAL, target_3r REAL, available_reward_risk REAL, risk_percent REAL, quality REAL, score REAL, score_parts TEXT, key_points TEXT, state TEXT, session TEXT, float_at_detection REAL, detected_at TEXT, last_seen_at TEXT, outcome TEXT NOT NULL DEFAULT 'open', resolved_at TEXT, max_favorable_r REAL, max_adverse_r REAL, UNIQUE (ticker, pattern, direction, timeframe, entry))` — `entry` rounded to 4 decimals before storing. Table `ticker_scans(ticker PK, scanned_at TEXT)`.
  - `@dataclass(frozen=True) class SetupRecord` mirroring the columns (`score_parts: dict[str, float]`, `key_points: list[tuple[datetime, float]]`).
  - `def record_match(conn, ticker, match, plan, state, score, session: str, float_millions: float | None, now: datetime) -> SetupRecord` — insert, or on the unique key update plan/state/score/`last_seen_at` (keeps `detected_at`, `outcome`).
  - `def mark_ticker_scanned(conn, ticker, now) -> None`.
  - `def list_current_setups(conn, ticker: str | None = None) -> list[SetupRecord]` — records whose `last_seen_at` equals their ticker's `ticker_scans.scanned_at` and whose state isn't `invalidated`, ordered by score desc.
  - `def list_open_records(conn, ticker: str) -> list[SetupRecord]`; `def save_outcome(conn, record_id: int, resolution: Resolution) -> None`.
  - `resolver.py`: `Outcome = Literal["open", "target", "stop", "expired", "unresolved"]`; `@dataclass(frozen=True) class Resolution: outcome: Outcome; resolved_at: datetime | None; max_favorable_r: float | None; max_adverse_r: float | None`.
  - `def resolve_outcome(record: SetupRecord, bars: list[Bar], now: datetime) -> Resolution` — bars of the record's timeframe; walk bars after `detected_at`: entry fills when price trades through `entry`; after fill, stop if low ≤ stop (long), target if high ≥ `capped_target`; both in the same bar (including the fill bar) → `stop`. Track max favourable/adverse excursion in R after fill. Not filled by the deadline → `expired`; deadline passed while filled and neither hit → `expired`. Deadline: intraday 20:00 ET on `detected_at`'s Eastern date; daily the 20th daily bar after detection. If the earliest bar is later than `detected_at` (history trimmed) → `unresolved`. Otherwise `open`.

- [ ] **Step 1: Write failing tests**

```python
def test_record_match_twice_updates_existing_record(db_conn):  # same key -> one row, last_seen_at updated, detected_at kept
def test_entry_rounding_dedupes_float_noise(db_conn):  # 2.00000001 vs 2.0 -> one row
def test_list_current_setups_only_latest_scan(db_conn):  # record not seen in latest ticker scan excluded
def test_list_current_setups_excludes_invalidated(db_conn):
def test_resolve_target_hit_first():  # MFE 3.0
def test_resolve_stop_hit_first():   # MAE -1.0
def test_resolve_same_bar_records_stop():
def test_resolve_never_filled_expires_at_eight_pm():
def test_resolve_daily_expires_after_twenty_sessions():
def test_resolve_missing_history_is_unresolved():
def test_resolve_still_open_before_deadline():
def test_short_resolution_mirrors():
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(setups): record detected setups and resolve their outcomes`

---

### Task 10: Scanner and schedule

**Files:** Create `backend/app/scanning/__init__.py`, `scanning/active.py`, `scanning/snapshots.py`, `scanning/scanner.py`; modify `backend/app/db.py`, `backend/app/watchlist/scheduler.py`; Test `backend/tests/test_active_tickers.py`, `backend/tests/test_scanner.py`

**Interfaces:**
- Consumes: Tasks 1–9; `list_entries` (watchlist); `list_screens` is **not** used — "in a current screen result" means tickers in the latest feeder run's hits (`tickers_added + tickers_updated` from `get_last_feeder_run`).
- Produces:
  - `active.py`: `MAX_ACTIVE_TICKERS = 40`, `MIN_RELATIVE_VOLUME = 1.5`, `MIN_ABS_CHANGE_PERCENT = 5.0`; `def select_active_tickers(snapshots: list[ScreenRow], screen_hits: set[str]) -> list[str]` — active per Global Constraints; ordered by (in screen hits first, relative volume desc, max |change|/|AH change| desc); capped at 40.
  - `snapshots.py`: table `ticker_snapshots(ticker PK, data TEXT /* ScreenRow JSON */, fetched_at TEXT)`; `def save_snapshots(conn, rows: list[ScreenRow], now) -> None`; `def read_snapshots(conn) -> dict[str, tuple[ScreenRow, datetime]]`.
  - `scanner.py`:
    - `@dataclass(frozen=True) class ScanDeps: fetch_bars: Callable[[str, Interval], list[Bar]]; fetch_snapshots: Callable[[list[str]], list[ScreenRow]]`.
    - `@dataclass(frozen=True) class ScanResult: scanned: list[str]; failed: list[tuple[str, str]]; setups_found: int; scanned_at: datetime`.
    - `def scan_ticker(conn, ticker: str, snapshot: ScreenRow | None, now: datetime, deps: ScanDeps) -> int` — loads daily, 5m, 1m via `load_bars`; computes daily levels, session levels, VWAP; runs detectors per timeframe; builds plans (drops `None`), states, scores; records every match (short ones too); resolves this ticker's open records using the matching-timeframe bars; `mark_ticker_scanned`; returns matches recorded.
    - `def run_scan(conn, now: datetime, deps: ScanDeps, tickers: list[str] | None = None) -> ScanResult` — `None` = watchlist: fetch snapshots for all watchlist tickers, save them, select active; explicit list = scan those. Per-ticker Finviz errors (`FinvizAuthError`, `FinvizRateLimitError`, `FinvizUnavailableError`) go to `failed` with their message and the scan continues; `FinvizAuthError` stops the scan early (every later call would fail the same way) and is listed once.
    - Session label for records: `"pre-market" | "regular" | "after-hours"` from the detection bar's ET time (`"daily"` for daily).
  - `scheduler.py`: after a feeder tick that ran (inside the window), call `run_scan` with real deps in the same thread; log a WARNING listing failed tickers.

- [ ] **Step 1: Write failing tests** (fake `ScanDeps` returning fixture bars; one fixture produces a high-of-day break)

```python
def test_select_active_by_relative_volume_change_or_screen_hit():
def test_select_active_caps_at_forty_most_active_first():
def test_scan_ticker_records_detected_setup(db_conn):  # high_of_day_break row with plan fields
def test_scan_ticker_records_short_matches_too(db_conn):
def test_run_scan_continues_after_ticker_failure(db_conn):  # 2nd ticker raises FinvizUnavailableError -> failed lists it, 3rd scanned
def test_run_scan_stops_after_auth_failure(db_conn):
def test_run_scan_saves_watchlist_snapshots(db_conn):
def test_scheduled_tick_runs_scan_after_feeder(tmp_path):
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** full suite → PASS.
- [ ] **Step 5: Commit** `feat(scanning): scan active watchlist tickers after each feeder run`

---

### Task 11: API — bars, scans, setups, settings, watchlist prices

**Files:** Create `backend/app/routes/bars.py`, `routes/setups.py`, `routes/settings.py`; modify `routes/watchlist.py`, `schemas.py`, `main.py`; Test `backend/tests/test_setups_routes.py`, `backend/tests/test_settings_routes.py`, extend `test_watchlist_routes.py`

**Interfaces:**
- Produces:
  - `GET /api/bars/{ticker}?interval=1m|5m|daily` → `{bars: [{time, open, high, low, close, volume}], fetched_at, daily_levels: [{price, touches}], session: SessionLevels | null, vwap: [number|null] | null}` (levels/session/vwap so the chart can draw them; `session`/`vwap` null for daily). Unknown interval → 422.
  - `POST /api/scans` body `{ticker?: string}` → `{scanned, failed: [{ticker, reason}], setups_found, scanned_at}`.
  - `GET /api/setups` → `{setups: SetupOut[], warnings: SetupOut[], show_short_setups: bool}` — `setups` = current long records plus short records when the setting is on; `warnings` = current short records when it's off. Each `SetupOut` includes the plan fields, `state`, `score`, `score_parts`, `key_points`, `detected_at`, `last_seen_at`, `has_conflict: bool` (an opposite-direction current record exists for the ticker).
  - `GET /api/stocks/{ticker}/setups` → same shape filtered to the ticker.
  - `GET /api/settings` → `{show_short_setups: bool}`; `PUT /api/settings` same body; stored in `app_meta` key `show_short_setups`.
  - `WatchlistEntryOut` gains `snapshot: {price, change_percent, after_hours_change_percent, relative_volume, fetched_at} | null` from `ticker_snapshots`.
  - Finviz errors map with `finviz_error_to_http` (502/503/504).

- [ ] **Step 1: Write failing tests**

```python
def test_bars_route_returns_bars_levels_and_session():  # patch load_bars
def test_bars_route_rejects_unknown_interval():  # ?interval=2m -> 422
def test_scan_route_scans_one_ticker():  # patch run_scan, assert tickers=["HOST"]
def test_setups_hide_shorts_as_warnings_by_default():
def test_setups_include_shorts_when_setting_on():
def test_setups_flag_conflict_when_ticker_has_opposite_record():
def test_settings_round_trip():
def test_watchlist_entries_include_latest_snapshot():
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** full suite → PASS.
- [ ] **Step 5: Commit** `feat(api): expose bars, scans, ranked setups and settings`

---

### Task 12: Setups view

**Files:** Create `frontend/src/api/setups.ts`, `api/settings.ts`, `components/SetupsView.tsx`, `components/SetupsView.test.tsx`; modify `App.tsx`, `App.test.tsx`, `styles.css`

**Interfaces:**
- Consumes: Task 11 endpoints.
- Produces:
  - `api/setups.ts`: types `Setup`, `SetupsResponse`, `ScanResult`; `fetchSetups()`, `fetchStockSetups(ticker)`, `runScan(ticker?: string)`.
  - `api/settings.ts`: `fetchSettings()`, `saveSettings({ show_short_setups })`.
  - `<SetupsView onOpenStock={(ticker) => void} />`: "Scan watchlist" button (shows "Scanning…", then "12 scanned, 3 failed: …" with failures in `role="alert"`); "Show short setups" checkbox (saves the setting, reloads); ranked table — Ticker (button calling `onOpenStock`), Pattern (human name, e.g. "High-of-day break"), Timeframe, State, Entry, Stop, Target, R:R (e.g. "1.5R", with "capped by 2.15" when `blocking_level`), Risk %, Score (expand to show `score_parts`), conflict badge "Bearish pattern too"; below it "Bearish warnings" (pattern, timeframe, breakdown level) when shorts are hidden; empty state "No setups detected in the last scan. Scans run every 15 minutes from 4:00 AM to 8:00 PM ET, or scan now."
  - Pattern display names live in one map `PATTERN_NAMES` in `api/setups.ts`.
  - `App.tsx`: tabs "Setups" (default), "Screens", "Watchlist", "Stock"; `openStock(ticker)` switches to Stock with that ticker.

- [ ] **Step 1: Write failing tests**

```tsx
it("lists setups ranked with entry, stop, target and available R:R")
it("shows the blocking level when the target is capped")
it("lists bearish patterns as warnings when shorts are hidden")
it("saves the show-short-setups setting and reloads")
it("shows scan failures after scanning")
it("opens the stock view when a ticker is clicked")
```

- [ ] **Step 2: Run** `cd frontend && npm test` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `npx tsc -b` clean.
- [ ] **Step 5: Commit** `feat(frontend): add ranked setups view with scan and short-setup toggle`

---

### Task 13: Stock view with candle chart

**Files:** Create `frontend/src/api/bars.ts`, `chartTime.ts`, `chartTime.test.ts`, `components/CandleChart.tsx`, `components/CandleChart.test.tsx`, `components/StockView.tsx`, `components/StockView.test.tsx`; delete `components/LookupView.tsx`; modify `App.tsx`, `WatchlistView.tsx`, `ScreenResultsTable.tsx`, `package.json`, `styles.css`

**Interfaces:**
- Consumes: Task 11 `GET /api/bars`, `GET /api/stocks/{ticker}/setups`, Phase 1 `fetchQuote`.
- Produces:
  - `npm install lightweight-charts@^4.2.0`.
  - `chartTime.ts`: `toChartTime(isoTime: string): number` — Unix seconds shifted by the America/New_York UTC offset at that instant, so lightweight-charts (which labels in UTC) shows Eastern wall-clock times.
  - `<CandleChart bars levels={{price, label, kind: "level" | "entry" | "stop" | "target"}[]} outline={[time, price][] | null} vwap={(number|null)[] | null} />` — candlestick series; one `createPriceLine` per level (daily levels thin and muted, entry amber, stop red, target green); outline drawn as a line series; VWAP as a line series. Resizes with its container (`ResizeObserver`), removes the chart on unmount.
  - `<StockView ticker={string | null} onTickerChange />`: ticker search (Phase 1 `StockSearch`), timeframe switch 1m / 5m / daily (default 5m), the chart, a setup list for the ticker (clicking one draws its entry/stop/target and outline), Phase 1 quote table, "Open on Finviz" link, "Scan this stock" button (`runScan(ticker)` then reload), "Bars as of <time>" label.
  - Watchlist and screen-result tickers call `onOpenStock` (the Finviz link stays as a separate small "Finviz" link). Watchlist rows show Price, Change, After-hours, Rel vol from `snapshot`, with "as of <time>".

- [ ] **Step 1: Write failing tests** (`vi.mock("lightweight-charts")` with a fake `createChart` recording calls)

```tsx
it("toChartTime shifts by the Eastern offset in summer and winter")  // EDT -4h, EST -5h
it("CandleChart draws a price line for each level with its colour")
it("CandleChart removes the chart on unmount")
it("StockView loads 5m bars by default and switches timeframe")
it("StockView draws the selected setup's entry, stop and target")
it("StockView scans the stock and reloads its setups")
it("WatchlistView shows price and change from the latest snapshot")
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `npx tsc -b` clean.
- [ ] **Step 5: Verify visually**: `FRONTEND_PORT=5174 docker compose up --build -d`; screenshot Setups, Stock (5m and daily), Watchlist at 1440×900 and 390×844 with the scratchpad Playwright script; fix overflow/contrast issues found.
- [ ] **Step 6: Commit** `feat(frontend): add stock view with candle chart, levels and setup lines`

---

### Task 14: Sanity check, docs, decision records

**Files:** Modify `backend/scripts/finviz_sanity_check.py`, `backend/scripts/README.md`, `README.md`; create `docs/decisions/0003-lightweight-charts.md`, `docs/decisions/0004-scan-only-active-tickers.md`

**Interfaces:**
- `--bars TICKER`: fetches 1m, 5m and daily bars for real; prints count, first/last timestamp (ET), and checks the last 1m bar's Eastern date is today or the last trading day; then runs `scan_ticker` against a temporary SQLite file and prints matches.
- README: Setups and Stock tabs, how scans run (after each feeder run, max 40 active tickers, ~1 request/s), what "available R:R" and "capped by" mean, "Show short setups", outcome tracking, and that detection is rule-based and not advice.
- 0003: lightweight-charts v4 vs Recharts/Chart.js/v5 (purpose-built candles + price lines, small, Apache-2.0; v5 API changed — pinned to v4).
- 0004: scanning only active tickers (≤ 40) vs whole watchlist (request budget with no documented Finviz limits).

- [ ] **Step 1:** Implement the sanity mode; run it: `cd backend && set -a && . ../.env && set +a && .venv/bin/python -m scripts.finviz_sanity_check --bars HOST` → prints three bar counts and exits 0.
- [ ] **Step 2:** Write the docs and decision records.
- [ ] **Step 3: Verify** `cd backend && .venv/bin/python -m pytest -q` and `cd frontend && npm test && npx tsc -b` → all pass.
- [ ] **Step 4: Commit** `docs: document setups, stock view and scanning; record chart and scan-scope decisions`
