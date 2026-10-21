# Phase 2 Milestone 2b — More Patterns and Per-Stock Verdict Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the rest of the milestone-2 detectors (ascending/descending triangle, double
bottom/top, ABCD/inverse ABCD, micro pullback, first pullback/first bounce fail) and a
per-stock verdict (leans long / leans short / no clear edge, with reasons) shown on the
Setups, Watchlist and Stock views.

**Architecture:** Detectors are new plain functions on the existing registry
(`app/patterns/detectors/__init__.py`), sharing a small swing-point helper. The verdict is a
pure function (`app/patterns/verdict.py`) over bars, levels and the ticker's matches; the
scanner computes it per scanned ticker, stores it in `ticker_verdicts`, and stamps it on
newly recorded setups. Routes and views read it.

**Tech Stack:** unchanged (Python/FastAPI/SQLite, React/TS/Vitest). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md`
(section 3 core + momentum tables, 5a verdict, 5b "verdict at that moment", 7 UI).

## Global Constraints

- Same as milestone 2a (`docs/superpowers/plans/2026-10-21-phase2-m2a-setups-engine.md`
  Global Constraints): pure pattern code, direction-aware, shorts only as warnings while
  `show_short_setups` is off, Eastern sessions, `TARGET_R = 3`.
- Every detector: pure function `(bars, context) -> list[PatternMatch]`, quality 0–1 with
  named parts, `key_points` for the chart outline, at most one match per direction, entry
  and stop on correct sides (the trade plan rejects the rest anyway).
- Verdict values: `"leans_long" | "leans_short" | "no_clear_edge"`; "No clear edge" must be
  a common, honest answer — never force a call.
- Verdict is shown even when shorts are hidden (spec 5a: the user wants to know).

## Review Focus

1. Detectors on short or flat series (fewer bars than a lookback, all-equal prices) must
   return `[]`, not raise (each detector task: `test_..._returns_nothing_on_short_or_flat_bars`).
2. The first-pullback detector must only fire on the *first* pullback of the day after a
   gap, not on every later pullback (Task 5 `test_second_pullback_is_not_a_first_pullback`).
3. A verdict computed with missing inputs (no 1m bars today, no daily levels, no matches)
   must still return a value built only from what's available, and say so in its reasons
   (Task 6 `test_verdict_with_missing_inputs_uses_what_is_available`).
4. A stock with mixed signals must come out "no clear edge" (Task 6
   `test_mixed_signals_give_no_clear_edge`).
5. The verdict recorded on a setup is the one at first detection; later scans don't rewrite
   it (Task 7 `test_setup_keeps_verdict_from_first_detection`).

---

### Task 1: Moving averages and swing points

**Files:** Modify `backend/app/patterns/indicators.py`; create `backend/app/patterns/swings.py`;
Test `backend/tests/test_moving_averages.py`, `backend/tests/test_swings.py`

**Interfaces — Produces:**
- `def ema(values: list[float], period: int) -> list[float | None]` — `None` for the first
  `period - 1` values; seeded with the simple average of the first `period`; then
  `alpha = 2 / (period + 1)`.
- `def sma(values: list[float], period: int) -> list[float | None]`.
- `swings.py`: `@dataclass(frozen=True) class Swing: index: int; price: float; is_high: bool`;
  `def find_swings(bars: list[Bar], side_bars: int = 2) -> list[Swing]` — swing high: high
  strictly above the `side_bars` highs on each side; swing low likewise; ordered by index
  (a bar can be both).

- [ ] **Step 1: Tests** — `test_ema_seeds_with_simple_average` (`ema([1,2,3,4], 3) == [None, None, 2.0, 3.0]`),
  `test_sma_window`, `test_ema_shorter_than_period_is_all_none`, `test_find_swings_marks_highs_and_lows`,
  `test_find_swings_ignores_flat_stretches`, `test_find_swings_needs_full_window`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(patterns): add EMA/SMA and a shared swing-point finder`

---

### Task 2: Ascending and descending triangles

**Files:** Create `backend/app/patterns/detectors/triangles.py`; register in `detectors/__init__.py`; Test `backend/tests/test_triangle_detectors.py`

**Rules** (all timeframes; `TRIANGLE_LOOKBACK_BARS = 40`, `FLAT_TOLERANCE_PERCENT = 0.75`, `MIN_RISE_PERCENT = 0.3`):
- Ascending (`ascending_triangle`, long): within the lookback, ≥ 2 swing highs within the
  tolerance of the highest of them (flat top), and ≥ 2 swing lows after the first flat-top
  swing that each rise by ≥ `MIN_RISE_PERCENT` over the previous one. Last close no more
  than 5% below or 2% above the top. `entry` = highest flat-top swing; `stop` = most recent
  swing low.
- `quality_parts = {"touches": min(top swings / 4, 1), "rising_lows": min(rising lows / 3, 1), "contraction": 1 - (range of last third of window) / (range of first third), clamped 0–1}`.
- Descending (`descending_triangle`, short) mirrored: flat bottom, falling highs.

- [ ] **Step 1: Tests** — `test_ascending_triangle_detected`, `test_flat_top_with_flat_lows_is_not_ascending`,
  `test_ascending_triangle_ignored_far_below_top`, `test_descending_triangle_is_short`,
  `test_triangles_return_nothing_on_short_or_flat_bars`.
- [ ] **Steps 2–4:** RED → implement → GREEN.
- [ ] **Step 5: Commit** `feat(patterns): detect ascending and descending triangles`

---

### Task 3: Double bottom and double top

**Files:** Create `backend/app/patterns/detectors/doubles.py`; register; Test `backend/tests/test_double_detectors.py`

**Rules** (all timeframes; `DOUBLE_LOOKBACK_BARS = 60`, `MATCH_TOLERANCE_PERCENT = 2.0`, `MIN_SEPARATION_BARS = 5`,
`MIN_DEPTH_PERCENT = {"1m": 1.5, "5m": 2.5, "daily": 8.0}`):
- Double bottom (`double_bottom`, long): the two most recent swing lows L1, L2 (L2 after L1
  by ≥ 5 bars) within 2% of each other, with a swing high (neckline) between them at least
  `MIN_DEPTH_PERCENT` above the higher low. Last close below the neckline within 5%, or one
  of the last 3 bars closed above it (just broke). `entry` = neckline; `stop` = lower of
  L1, L2.
- `quality_parts = {"symmetry": 1 - |L1 - L2| / L1 / 0.02, "depth": min(depth / threshold / 2, 1), "volume_on_retest": 1.0 if volume at L2 < volume at L1 else 0.0}`.
- Double top (`double_top`, short) mirrored.

- [ ] **Step 1: Tests** — `test_double_bottom_detected_with_neckline_entry`, `test_double_bottom_rejects_lows_too_far_apart_in_price`,
  `test_double_bottom_needs_real_depth`, `test_double_top_is_short`, `test_doubles_return_nothing_on_short_or_flat_bars`.
- [ ] **Steps 2–4.** **Step 5: Commit** `feat(patterns): detect double bottoms and double tops`

---

### Task 4: Momentum ABCD and inverse ABCD

**Files:** Create `backend/app/patterns/detectors/abcd.py`; register (intraday only); Test `backend/tests/test_abcd_detectors.py`

**Rules** (my call — the momentum day-trading form, not the harmonic AB=CD):
`ABCD_LOOKBACK_BARS = 60`, `MIN_SPIKE_PERCENT = {"1m": 3.0, "5m": 5.0}`, `RETRACE_RANGE = (0.3, 0.7)`.
- Long (`abcd`): A = highest swing high in the lookback, reached by a spike of ≥
  `MIN_SPIKE_PERCENT` from the lowest low before it; B = lowest swing low after A,
  retracing 30–70% of the spike; C = a swing high after B, below A; D = lowest low after C,
  which must stay above B (higher low). Needs ≥ 1 bar after C. Last close ≤ 2% above C.
  `entry` = C; `stop` = D.
- `quality_parts = {"retrace": 1 - |retrace - 0.5| / 0.2 clamped, "higher_low": min((D - B) / (C - B) * 2, 1), "volume": spike volume vs pullback volume as in flags}`.
- Short (`inverse_abcd`) mirrored.
- `key_points` = [(A), (B), (C), (D)].

- [ ] **Step 1: Tests** — `test_abcd_detected_with_c_entry_and_d_stop`, `test_abcd_rejects_lower_low_at_d`,
  `test_abcd_rejects_retrace_too_deep`, `test_inverse_abcd_is_short`, `test_abcd_not_run_on_daily`,
  `test_abcd_returns_nothing_on_short_or_flat_bars`.
- [ ] **Steps 2–4.** **Step 5: Commit** `feat(patterns): detect momentum ABCD and inverse ABCD`

---

### Task 5: Micro pullback, first pullback, first bounce fail

**Files:** Create `backend/app/patterns/detectors/pullbacks.py`; register (intraday only); Test `backend/tests/test_pullback_detectors.py`

**Rules:**
- Micro pullback (`micro_pullback`, long only): the last 1–2 bars are the pullback (each
  low ≥ the run's top bar low − tiny, i.e. retrace ≤ 40% of the run) after a run of ≥ 3
  bars with rising closes gaining ≥ `{"1m": 2.0, "5m": 3.0}`%. `entry` = pullback's highest
  high; `stop` = pullback's lowest low. `quality_parts = {"run_strength", "shallow", "volume_drop"}`.
- First pullback (`first_pullback`, long): today gapped up ≥ `GAP_PERCENT = 4.0` (today's
  first bar open vs previous close from the context); after today's open price made a new
  session high H, then pulled back for ≥ 2 bars (lower highs), and this is the **first**
  such pullback of the day (no earlier swing low today after a new high). Relevant while the
  last bar is in the pullback or its high was just taken out. `entry` = high of the last
  pullback bar; `stop` = pullback low.
- First bounce fail (`first_bounce_fail`, short): mirror on a ≥ 4% gap down.

- [ ] **Step 1: Tests** — `test_micro_pullback_after_strong_run`, `test_micro_pullback_rejects_deep_pullback`,
  `test_first_pullback_after_gap_up`, `test_no_first_pullback_without_gap`,
  `test_second_pullback_is_not_a_first_pullback`, `test_first_bounce_fail_after_gap_down`,
  `test_pullbacks_return_nothing_on_short_or_flat_bars`.
- [ ] **Steps 2–4.** **Step 5: Commit** `feat(patterns): detect micro pullbacks and first pullbacks after gaps`

---

### Task 6: Per-stock verdict

**Files:** Create `backend/app/patterns/verdict.py`; Test `backend/tests/test_verdict.py`

**Interfaces — Produces:**
- `VerdictCall = Literal["leans_long", "leans_short", "no_clear_edge"]`.
- `@dataclass(frozen=True) class Verdict: call: VerdictCall; score: float; parts: dict[str, float]; reasons: list[str]`.
- `def compute_verdict(intraday_1m: list[Bar], intraday_5m: list[Bar], daily: list[Bar], vwap_1m: list[float | None] | None, daily_levels: list[PriceLevel], matches: list[PatternMatch]) -> Verdict`.
- Parts, each −1…+1 (absent inputs are skipped and named in reasons as "no data"):
  - `trend`: mean of signs of: last 1m close vs VWAP; vs EMA 9 and EMA 20 on 1m; vs EMA 9 and
    EMA 20 on 5m; daily close vs SMA 20 and SMA 50.
  - `volume`: over the last 20 1m bars, (up-bar volume − down-bar volume) / total.
  - `location`: room to the nearest daily level above vs below the last price:
    `(up_room − down_room) / (up_room + down_room)`; a missing side counts as 20% room.
  - `patterns`: (Σ quality of long matches − Σ quality of short) / Σ quality of all; 0 if none.
- `WEIGHTS = {"trend": 0.35, "patterns": 0.30, "volume": 0.20, "location": 0.15}` over the
  parts present (renormalised); `score` = weighted sum; `call` = leans_long if score ≥
  `CALL_THRESHOLD = 0.25`, leans_short if ≤ −0.25, else no_clear_edge.
- `reasons`: one short plain sentence per part, e.g. "Above VWAP and rising EMAs",
  "Volume heavier on down bars", "Little room to the 3.07 resistance", "2 bullish patterns,
  1 bearish"; ordered by absolute contribution.

- [ ] **Step 1: Tests** — `test_uptrend_with_bull_patterns_leans_long`, `test_downtrend_with_bear_patterns_leans_short`,
  `test_mixed_signals_give_no_clear_edge`, `test_verdict_with_missing_inputs_uses_what_is_available`,
  `test_reasons_are_ordered_by_contribution`.
- [ ] **Steps 2–4.** **Step 5: Commit** `feat(patterns): compute a per-stock long/short verdict with reasons`

---

### Task 7: Store verdicts during scans

**Files:** Modify `backend/app/db.py`, `backend/app/scanning/scanner.py`, `backend/app/setups/store.py`; create `backend/app/scanning/verdicts.py`; Test `backend/tests/test_verdict_store.py`, extend `test_scanner.py`, `test_setup_store.py`

**Interfaces — Produces:**
- Table `ticker_verdicts(ticker PK, call TEXT, score REAL, parts TEXT, reasons TEXT, computed_at TEXT)`;
  `save_verdict(conn, ticker, verdict, now)`, `read_verdicts(conn) -> dict[str, tuple[Verdict, datetime]]`.
- `setup_records.verdict TEXT` (call at first detection; not updated on conflict);
  `record_match(..., verdict: VerdictCall | None)` keyword argument, default `None`.
- `scan_ticker` computes the verdict after detection (only today's intraday bars count;
  stale-day series are passed as empty), saves it, and passes its call to `record_match`.

- [ ] **Step 1: Tests** — `test_scan_ticker_saves_verdict`, `test_setup_keeps_verdict_from_first_detection`, `test_verdict_round_trip`.
- [ ] **Steps 2–4.** **Step 5: Commit** `feat(scanning): store each scanned stock's verdict`

---

### Task 8: Verdict in the API and views; new pattern names

**Files:** Modify `backend/app/schemas.py`, `routes/setups.py`, `routes/watchlist.py`; create route `GET /api/stocks/{ticker}/verdict`;
frontend `api/setups.ts`, `api/watchlist.ts`, `components/SetupsView.tsx`, `WatchlistView.tsx`, `StockView.tsx`, `styles.css` and their tests

**Interfaces — Produces:**
- `VerdictOut {call, score, parts, reasons, computed_at}`; `SetupOut.verdict: VerdictOut | null`
  (ticker's latest); `WatchlistEntryOut.verdict: VerdictOut | null`;
  `GET /api/stocks/{ticker}/verdict` → `VerdictOut | null`.
- Frontend `PATTERN_NAMES` adds: ascending_triangle "Ascending triangle",
  descending_triangle "Descending triangle", double_bottom "Double bottom", double_top
  "Double top", abcd "ABCD", inverse_abcd "Inverse ABCD", micro_pullback "Micro pullback",
  first_pullback "First pullback", first_bounce_fail "First bounce fail".
- `<VerdictBadge verdict />`: "Leans long" (green), "Leans short" (red), "No clear edge"
  (muted); title attribute lists reasons. Shown in a Setups column, a Watchlist column, and
  at the top of the Stock view with the reasons listed underneath.

- [ ] **Step 1: Tests** — backend `test_stock_verdict_route`, `test_setups_include_ticker_verdict`;
  frontend `it("shows each setup's stock verdict")`, `it("shows the verdict and its reasons on the stock view")`,
  `it("shows verdicts on the watchlist")`, `it("names the new patterns")`.
- [ ] **Steps 2–4.** **Step 5: Commit** `feat: show per-stock verdicts and the new patterns`

---

### Task 9: Docs and live check

**Files:** `README.md`, `backend/scripts/finviz_sanity_check.py` (`--bars` also prints the verdict)

- [ ] README: new patterns list, what the verdict means and its inputs, "no clear edge" is normal.
- [ ] Live: stop the backend container, run `--bars` on a mover, restart; screenshot Setups,
  Stock and Watchlist at desktop/phone sizes; fix layout issues found.
- [ ] Commit `docs: document new patterns and the per-stock verdict`
