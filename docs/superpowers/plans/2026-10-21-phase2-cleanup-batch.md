# Phase 2 Cleanup Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the minor findings deferred by the milestone 1, 2a and 2b reviews.

**Architecture:** No new structure; each fix lands in the module that owns the behaviour.

**Tech Stack:** unchanged. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md`.
Source of the items: the "Deferred minors" lists reported at the end of each milestone.

## Global Constraints

- Every fix has a test that fails before it and passes after (`.claude/rules/fixing-a-bug.md`).
- Behaviour changes visible to the user go in the README in the same commit.
- Same pattern/verdict/shorts constraints as milestones 2a and 2b.

## Review Focus

1. The scan lock must never stay held after a failed scan (Task 3 `test_scan_lock_released_after_error`).
2. Trimming short plans from `warnings` must not break the Stock view's warning display (Task 7).
3. Verdict changes must keep "no clear edge" the honest default when inputs are thin or disagree (Task 6).

---

### Task 1: Data robustness

- `get_bars` sorts bars by time before returning (Finviz order isn't guaranteed; the chart
  throws on unordered times). Test `test_get_bars_returns_bars_oldest_first_even_if_unsorted`.
- Phase 1 `GET /api/stocks/{ticker}` maps `FinvizRateLimitError` → 503 and
  `FinvizUnavailableError` → 504 via `finviz_error_to_http`. Tests for both.

### Task 2: Screens

- Saving a screen checks with Finviz only pasted codes and a signal that are new compared
  with the stored screen (renames and feeder toggles make no Finviz requests). Test
  `test_update_only_checks_new_codes`.
- `POST /api/screens/parse-url` returns `ignored_params: list[str]` naming query
  parameters other than `f`, `s`, `o`, `v` (e.g. `t`); the editor shows "Finviz URL parts not
  used: t". Tests backend + editor.
- The editor notes under the sort line: "Sort order isn't checked with Finviz." (order codes
  can't be verified by row count). Editor test.
- A feeder screen adds at most `MAX_FEEDER_HITS_PER_SCREEN = 100` rows per run (in Finviz's
  order); when capped, `failed_screens` gets `(name, "returned N stocks; only the first 100
  were added — narrow the screen")`. Test `test_feeder_caps_hits_per_screen`.

### Task 3: Watchlist and scheduling

- Watchlist expiry runs on every feeder-loop tick, inside or outside the 04:00–20:00 window
  (`run_scheduled_expiry`). Test: Saturday tick expires a 91-day-old entry.
- Appearance history includes the screen name (`AppearanceOut.screen_name: str | None`,
  `None` if the screen was deleted); the watchlist history line reads
  "2026-10-20: +47.40% (Top gainers — low float)". Backend + frontend tests.
- The feeder loop skips its immediate startup tick when the last feeder run finished less
  than one interval ago (uvicorn `--reload` restarts the lifespan on every code change).
  Test `test_startup_tick_skipped_when_recent_run_exists`.
- A process-wide non-blocking scan lock (`app/scanning/lock.py`, `threading.Lock`):
  `POST /api/scans` returns 409 "A scan is already running; try again when it finishes"
  if held; the scheduled scan skips (logs info) if held. Released in `finally`. Tests
  `test_second_scan_request_gets_409`, `test_scan_lock_released_after_error`.

### Task 4: Scanner and plans

- `trailing_stop` is only suggested when it lies between the plan's stop and the current
  price (last close); otherwise `None`. Tests long and short.
- Daily setups' state uses the latest intraday close from today (1m, else 5m) when
  available, not the cached daily close. Test with stale daily close vs fresh 1m.
- An auth failure lists the remaining tickers as skipped (same as rate limiting):
  `("BBB, CCC", "skipped: Finviz rejected the auth token")`. Test.

### Task 5: Detector edges

- Micro pullback: the run walk-back stops at an Eastern date change, and every pullback bar's
  high must stay ≤ the run's top (a new high is a breakout, not a pullback). Tests.
- ABCD on any intraday timeframe only uses today's bars (Eastern date of the last bar).
  Test with yesterday's after-hours low before today's spike.

### Task 6: Verdict weighting

- Minimum evidence: if the available parts' total weight is < `MIN_WEIGHT_FOR_CALL = 0.5`,
  the call is `no_clear_edge` and the first reason is "Not enough data for a call".
- Disagreement: if `trend` and `patterns` are both present with opposite signs and each
  |value| ≥ 0.5, the call is `no_clear_edge` with the reason "Trend and patterns disagree".
- Location: both sides' room is capped at `MAX_LEVEL_ROOM = 0.20` (20%), so distant support
  no longer reads as bearish for a stock with no resistance overhead.
- Relative volume: `compute_verdict(..., relative_volume: float | None = None)`; the volume
  part is scaled by `min(relative_volume / 1.5, 1)` when known, and the reason names it
  ("on 3.2x relative volume"). The scanner passes the snapshot's value.
- Tests for each, plus the existing verdict tests stay green (adjust only fixtures whose
  inputs are now thin, and say so in the ledger).

### Task 7: API and UI

- `warnings` in `GET /api/setups` / `GET /api/stocks/{ticker}/setups` use a `WarningOut`
  model without stop, targets, partials, trailing stop or R:R (entry is the breakdown
  level). Frontend `Warning` type; Setups and Stock views updated. Tests backend + frontend.
- Conflict badge is direction-aware: long rows "Bearish pattern too", short rows "Bullish
  pattern too". Test.
- Stock view ignores responses for a ticker/timeframe that is no longer selected (a
  cancelled flag in each effect). Test: switch A→B with A resolving last; B stays shown.
- Typed dicts in `routes/setups.py` and `routes/watchlist.py`
  (`dict[str, tuple[Verdict, datetime]]`, snapshots likewise).

Each task: tests first (RED), implement (GREEN), full suites, commit.
