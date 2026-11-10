# Trade Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Journal tab plus Log trade / Pass panels on the Stock page that record real trades (any number of fills) and passes (with reasons), save each trade's 1-minute bars, and summarise results.

**Architecture:** Backend package `app/journal/` holds pure calculation modules (positions, pass scoring, review, summary) tested without a database, a store module for SQLite, and a bar-saving module. Routes in `app/routes/journal.py`. Every figure the UI shows comes from the backend, including the live preview while typing fills, so the frontend never re-implements P&L maths. Setup history is a new append-only table written by `record_match`.

**Tech Stack:** FastAPI + pydantic v2 + SQLite (backend), React 18 + TypeScript + lightweight-charts 4.2 + vitest (frontend). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-09-trade-journal-design.md`

## Global Constraints

- No new dependencies (backend or frontend).
- Times stored as ISO strings with offset (follow existing code: Eastern-offset or UTC both parse with `datetime.fromisoformat`); shown in ET.
- Ticker validation: `^[A-Za-z.\-]{1,10}$` (existing `TICKER_PATTERN`), upper-cased.
- Limits: ≤ 50 fills per trade; notes ≤ 1,000 chars; shares whole numbers 1–10,000,000; prices > 0 and ≤ 100,000; fees ≥ 0 and ≤ 10,000.
- Bars saved: 1-minute, 04:00–20:00 ET, per (ticker, trading day); status `partial` / `complete` / `missing`.
- Journal entries save even when Finviz fails.
- Pass reason keys and mistake keys are fixed lists served by the backend.
- Follow `.claude/rules/` (TDD, no `any`, validate at boundary, README in the same diff, conventional commits ending with the Co-Authored-By line).

## Review Focus

1. Logging a trade while Finviz is down or rate-limited → entry saves, bars marked pending, UI says "will retry".
2. A trade logged > 2 weeks after it happened → entry saves, days marked `missing`, chart says bars are gone.
3. Scaling out across two days / partial exits → P&L booked per closing-fill date; trade counted in the period of its last fill; daily loss uses today's closing fills only.
4. Fills that would take the position below zero or flip sides, or start with a closing side → rejected with a clear message.
5. CSV export of notes beginning with `=`, `+`, `-`, `@` → escaped with a leading `'`.

---

### Task 1: Setup history

**Files:**
- Modify: `backend/app/db.py` (new table `setup_history`)
- Modify: `backend/app/setups/store.py`
- Test: `backend/tests/test_setup_store.py`

**Interfaces:**
- Produces:
  - table `setup_history(id INTEGER PK, setup_record_id INTEGER NOT NULL REFERENCES setup_records(id) ON DELETE CASCADE, seen_at TEXT NOT NULL, score REAL NOT NULL, state TEXT NOT NULL, verdict TEXT, sliding_scale TEXT)` + index on `(setup_record_id, seen_at)`.
  - `@dataclass(frozen=True) SetupValues(score: float, state: SetupState, verdict: str | None, sliding_scale: SlidingScale | None)`
  - `setup_values_at(conn, record_id: int, at: datetime) -> SetupValues | None` — last history row with `seen_at <= at`; falls back to the record's own values when there is no history row at all; None if the record doesn't exist.
  - `list_setups_for_day(conn, ticker: str, day: date) -> list[SetupRecord]` — every record for the ticker whose `detected_at` (ET) is on `day` or that was still open on `day` (last_seen_at on that day), any outcome, ordered by detected_at.
  - `get_setup_record(conn, record_id: int) -> SetupRecord | None`

- [ ] **Step 1: Failing tests** — `test_record_match_appends_history_when_values_change` (two calls with different score → 2 history rows), `test_record_match_skips_history_when_nothing_changed` (same values twice → 1 row), `test_setup_values_at_returns_values_seen_before_time` (score 70 at 10:00, 85 at 10:15 → at 10:10 returns 70), `test_setup_values_at_falls_back_to_record_without_history`, `test_list_setups_for_day_includes_resolved_setups` (one stopped, one open → both).
- [ ] **Step 2:** Run `cd backend && .venv/bin/python -m pytest tests/test_setup_store.py -q` → new tests FAIL.
- [ ] **Step 3:** Implement. In `record_match`, after the upsert, read the last history row for the record and insert a new one (seen_at = `now`) when score, state, verdict or encoded sliding_scale differ. `verdict` passed to `record_match` is the current scan's call, stored in history (the record's own `verdict` column keeps its first value).
- [ ] **Step 4:** Run the file again → PASS; run full backend suite → PASS.
- [ ] **Step 5:** Commit `feat(setups): keep a history of each setup's score and grade`.

### Task 2: Position maths (pure)

**Files:**
- Create: `backend/app/journal/__init__.py`, `backend/app/journal/positions.py`
- Test: `backend/tests/test_journal_positions.py`

**Interfaces:**
- Produces:
  - `Direction = Literal["long", "short"]`, `Side = Literal["buy", "sell"]`
  - `@dataclass(frozen=True) Fill(side: Side, time: datetime, price: float, shares: int)`
  - `@dataclass(frozen=True) ClosedPnl(time: datetime, pnl: float)` — realised P&L of one closing fill (fees not included).
  - `@dataclass(frozen=True) TradeFigures(status: Literal["open","closed"], average_entry: float, average_exit: float | None, shares_held: int, max_shares: int, money_in: float, total_bought: float, realised_pnl: float, closed_pnl: list[ClosedPnl], fees: float, net_pnl: float, r_multiple: float | None, planned_reward_risk: float | None, opened_at: datetime, last_fill_at: datetime, duration_seconds: float)`
  - `validate_fills(direction: Direction, fills: list[Fill]) -> str | None` — error message or None.
  - `compute_trade_figures(direction, fills, plan_stop: float | None, plan_target: float | None, fees: float, now: datetime) -> TradeFigures` (fills already valid; sorted by time inside).

Rules (from spec): opening side = buy for long, sell for short. Average-cost method. `money_in` = max over time of shares held × current average entry. `net_pnl = realised_pnl - fees` (fees subtracted once the trade is closed; while open `net_pnl = realised_pnl`). R = net_pnl ÷ (|first fill price − plan_stop| × max_shares); None without a stop or when that risk is 0. Planned R:R = |target − first price| ÷ |first price − stop|. Duration: first fill → last fill, or → `now` while open.

Validation messages (exact): `"Add at least one fill."`, `"The first fill must be a buy for a long trade."` / `"... a sell for a short trade."`, `"Fill at {time} would sell more shares than are held."` (long; for short: "buy more shares than are short"), `"A trade can have at most 50 fills."`, `"Shares go back to zero before the last fill; log the rest as a new trade."`

- [ ] **Step 1: Failing tests:**
  - `test_simple_long_win`: buy 100 @ 2.00, sell 100 @ 2.50, stop 1.90, target 2.30 → net_pnl 50.0, r_multiple 5.0, planned_reward_risk 3.0, status closed, money_in 200.0.
  - `test_scale_in_and_out_uses_average_cost`: buy 100 @ 2.00, buy 100 @ 2.20, sell 100 @ 2.40, sell 100 @ 2.30 → average_entry 2.10, average_exit 2.35, realised 50.0, max_shares 200, money_in 420.0, closed_pnl = [30.0, 20.0].
  - `test_short_trade_profits_when_price_falls`: sell 100 @ 5, buy 100 @ 4.5 → net_pnl 50.0.
  - `test_open_trade_reports_shares_held_and_no_fees_yet`: buy 100, sell 40, fees 2 → status open, shares_held 60, net_pnl == realised_pnl.
  - `test_fees_reduce_closed_pnl`.
  - `test_no_stop_means_no_r`.
  - `test_validate_rejects_overselling`, `test_validate_rejects_wrong_opening_side`, `test_validate_rejects_reentry_after_flat`, `test_validate_rejects_more_than_50_fills`, `test_validate_accepts_partial_exits`.
- [ ] **Step 2:** Run `pytest tests/test_journal_positions.py -q` → FAIL (module missing).
- [ ] **Step 3:** Implement `positions.py`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(journal): add position maths for trades with any number of fills`.

### Task 3: Reasons, schema and store

**Files:**
- Create: `backend/app/journal/reasons.py`, `backend/app/journal/store.py`
- Modify: `backend/app/db.py` (tables)
- Test: `backend/tests/test_journal_store.py`

**Interfaces:**
- Produces:
  - `reasons.py`: `PASS_REASON_GROUPS: list[tuple[str, list[tuple[str, str]]]]` (group label, [(key, label)]) exactly the spec list; `MISTAKES: list[tuple[str, str]]`; `PASS_REASON_KEYS: frozenset[str]`; `MISTAKE_KEYS: frozenset[str]`; `OTHER_REASON = "other"`; `FOLLOWED_PLAN = "followed_plan"`.
  - Tables:
    - `journal_entries(id PK, kind TEXT CHECK IN ('trade','pass'), ticker, direction TEXT CHECK IN ('long','short'), created_at, updated_at, decided_at TEXT NOT NULL /* first fill time or pass time */, setup_record_id INTEGER REFERENCES setup_records(id) ON DELETE SET NULL, setup TEXT /* JSON snapshot or NULL */, stock TEXT NOT NULL /* JSON facts */, plan_stop REAL, plan_target REAL, fees REAL NOT NULL DEFAULT 0, reasons TEXT NOT NULL DEFAULT '[]', mistakes TEXT NOT NULL DEFAULT '[]', note TEXT NOT NULL DEFAULT '', pass_price REAL)`
    - `journal_fills(id PK, entry_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE, side TEXT CHECK IN ('buy','sell'), time TEXT NOT NULL, price REAL NOT NULL, shares INTEGER NOT NULL)`
    - `journal_bar_days(ticker TEXT, day TEXT /* YYYY-MM-DD ET */, status TEXT CHECK IN ('partial','complete','missing'), saved_at TEXT, bars TEXT NOT NULL DEFAULT '[]', PRIMARY KEY (ticker, day))`
  - `@dataclass(frozen=True) SetupSnapshot(setup_record_id: int, pattern: str, timeframe: str, direction: str, entry: float, stop: float, target: float, reward_risk: float, score: float, state: str, verdict: str | None, sliding_scale: SlidingScale | None)`
  - `@dataclass(frozen=True) StockFacts(company, country, sector, industry: str | None; market_cap_millions, float_millions, price, change_percent: float | None; volume_so_far: int | None; volume_vs_average: float | None)`
  - `@dataclass(frozen=True) JournalEntry(id, kind, ticker, direction, created_at, updated_at, decided_at: datetime, setup: SetupSnapshot | None, stock: StockFacts, plan_stop, plan_target: float | None, fees: float, reasons: list[str], mistakes: list[str], note: str, pass_price: float | None, fills: list[Fill])`
  - `@dataclass(frozen=True) NewEntry` — same fields minus id/created/updated.
  - `create_entry(conn, entry: NewEntry, now) -> JournalEntry`, `update_entry(conn, entry_id, entry: NewEntry, now) -> JournalEntry | None`, `delete_entry(conn, entry_id) -> bool`, `get_entry(conn, entry_id) -> JournalEntry | None`, `list_entries(conn, kind: Literal["trade","pass"] | None = None) -> list[JournalEntry]` (newest decided_at first), `find_open_trade(conn, ticker) -> JournalEntry | None` (computed via `compute_trade_figures` status).
- [ ] **Step 1: Failing tests:** round-trip create/get with fills and snapshots; update replaces fills; delete cascades fills; list orders newest first and filters by kind; `find_open_trade` returns the trade with shares held and ignores closed ones; `test_reason_keys_are_unique_and_include_other`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run file + full backend suite → PASS.
- [ ] **Step 5:** Commit `feat(journal): store trades, passes and their fills`.

### Task 4: Saved bars

**Files:**
- Create: `backend/app/journal/bars.py`
- Test: `backend/tests/test_journal_bars.py`

**Interfaces:**
- Consumes: `FetchBars` from `app/bars/loader.py`, `Bar`, `EASTERN`, `JournalEntry` (Task 3), `compute_trade_figures` (Task 2).
- Produces:
  - `DAY_END = time(20, 0)`; `BarDayStatus = Literal["partial","complete","missing"]`
  - `days_needed(entry: JournalEntry, now: datetime) -> list[date]` — weekdays from decided_at's ET date to last fill's date (or today while an open trade); a pass needs its own day.
  - `save_bar_days(conn, ticker, days: list[date], now, fetch_bars_fn: FetchBars) -> None` — skips days already `complete`/`missing`; one `fetch_bars_fn(ticker, "1m")` call; for each day: bars on that day → `complete` if `now` ≥ that day's 20:00 ET else `partial`; no bars and day older than the oldest fetched bar's day → `missing`; no bars otherwise → leave unsaved (holiday/no trading → `missing` once day is past and newer bars exist). Raises Finviz errors to the caller.
  - `read_bars(conn, ticker, days: list[date]) -> tuple[list[Bar], dict[date, BarDayStatus | None]]`
  - `save_bars_for_entry(conn, entry, now, fetch_bars_fn) -> str | None` — wraps save_bar_days; returns a user-facing warning (`"Chart bars not saved yet, will retry."`) on Finviz error instead of raising.
  - `complete_pending_days(conn, now, fetch_bars_fn) -> int` — for every entry whose needed days are not all complete/missing, save them; returns count of tickers fetched; stops on rate-limit/auth error.
- [ ] **Step 1: Failing tests** (fake `fetch_bars_fn`): saves only 04:00–20:00 bars of the day; partial before 8 PM then complete after rerun; missing when the fetched history starts after the day; Finviz error returns warning and leaves nothing saved; `complete_pending_days` completes a partial day; multi-day open trade needs every weekday through today.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(journal): save each trade's minute bars while Finviz still has them`.

### Task 5: Facts at trade time, pass scoring, review

**Files:**
- Create: `backend/app/journal/snapshot.py`, `backend/app/journal/pass_scoring.py`, `backend/app/journal/review.py`
- Test: `backend/tests/test_journal_snapshot.py`, `backend/tests/test_journal_pass_scoring.py`, `backend/tests/test_journal_review.py`

**Interfaces:**
- Produces:
  - `snapshot.py`:
    - `stock_facts_at(bars: list[Bar], previous_close: float | None, at: datetime, quote: dict | None, snapshot_row: dict | None) -> StockFacts` — price = close of last bar ≤ `at` (overridden by caller with the fill price for trades), change % vs previous_close, volume_so_far = sum of that ET day's bar volumes ≤ at, volume_vs_average = volume_so_far ÷ average volume (snapshot row `average_volume`, in thousands per Finviz → ×1000). company/country/sector/industry/market cap from quote keys `Company`, `Country`, `Sector`, `Industry`, `Market Cap`; float from the ticker snapshot.
    - `previous_close(daily_bars: list[Bar], day: date) -> float | None`.
    - `setup_snapshot(record: SetupRecord, values: SetupValues | None) -> SetupSnapshot`.
  - `pass_scoring.py`: `PassOutcome = Literal["target","stop","never_filled","undecided","not_scored"]`; `@dataclass(frozen=True) PassScore(outcome: PassOutcome, r: float | None)`; `score_pass(setup: SetupSnapshot | None, pass_time: datetime, pass_price: float | None, bars: list[Bar]) -> PassScore` — rules from spec "Scoring a pass": only bars after pass_time and before 20:00 ET that day; entry = pass_price if already beyond setup.entry (long: pass_price ≥ entry) else wait for entry; stop wins on a bar touching both; target R = |target − entry used| ÷ |entry used − stop|.
  - `review.py`:
    - `@dataclass(frozen=True) AfterExit(best_r: float | None, worst_r: float | None, best_price: float | None, worst_price: float | None)`; `after_exit(direction, figures: TradeFigures, plan_stop, bars) -> AfterExit | None` — None while open; bars after last fill until 20:00 ET of that day; R uses |first price − stop| per share, else None (prices still given).
    - `PlanFlag = Literal["exited_before_target","held_past_stop","followed_plan"]`; `plan_flags(direction, figures, plan_stop, plan_target, fills, bars) -> list[PlanFlag]` — held_past_stop: any bar while shares held with low < stop (long) / high > stop (short); exited_before_target: closed and average_exit short of target; followed_plan when neither.
- [ ] **Step 1: Failing tests:** facts from bars (price, change %, volume so far, vs average); pass already past entry uses pass price; pass waiting for entry that never fills → never_filled; stop-first on a two-sided bar; after-exit best/worst R; held_past_stop detection; followed_plan when exited at target.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement the three modules.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(journal): record facts at trade time and score passes and exits`.

### Task 6: Summary (pure)

**Files:**
- Create: `backend/app/journal/summary.py`
- Test: `backend/tests/test_journal_summary.py`

**Interfaces:**
- Consumes: Tasks 2, 3, 5; `PatternStats` from `app/setups/track_record.py`.
- Produces:
  - `Period = Literal["today","week","month","all"]`; `period_start(period, now) -> datetime | None` (ET midnight today; Monday of this week; 1st of month).
  - `@dataclass(frozen=True) ReviewedTrade(entry: JournalEntry, figures: TradeFigures, after: AfterExit | None, flags: list[PlanFlag])`, `ScoredPass(entry, score: PassScore)`.
  - `@dataclass(frozen=True) Bucket(label: str, count: int, pnl: float)`
  - `@dataclass(frozen=True) PnlPoint(time: datetime, pnl: float, cumulative: float)`
  - `@dataclass(frozen=True) PassReasonRow(reason: str, count: int, target: int, stop: int, never_filled: int, undecided: int, average_r: float | None)`
  - `@dataclass(frozen=True) VersusRow(pattern, timeframe, trades: int, win_rate: float|None, average_r: float|None, system: PatternStats | None, system_has_enough_history: bool)`
  - `@dataclass(frozen=True) JournalSummary(net_pnl, trades, wins, losses, win_rate, average_gain, average_loss, largest_win, largest_loss, average_planned_reward_risk, average_r, average_duration_seconds, average_sykes_points, average_sykes_letter, average_score, average_left_on_table_r, passes, open_trades: int, pnl_points: list[PnlPoint], by_country, by_industry, by_pattern, by_mistake, by_time_of_day, by_duration: list[Bucket], pass_reasons: list[PassReasonRow], versus_system: list[VersusRow])`
  - `summarise(trades: list[ReviewedTrade], passes: list[ScoredPass], start: datetime | None, system_stats: Callable[[str, str], PatternStats | None]) -> JournalSummary`
  - `daily_realised_pnl(trades: list[ReviewedTrade], now) -> float` — sum of today's (ET) `closed_pnl` minus fees of trades whose last fill is today.
  - Time-of-day buckets by opened_at ET: `4:00–9:30`, `9:30–10`, `10–11`, `11–12`, `12–2`, `2–4`, `4–8 PM`. Duration buckets: `Under 5 min`, `5–30 min`, `30 min to close` (same day), `Multi-day`. Sykes letter from average points with the existing thresholds in `app/patterns/sliding_scale.py`.
- [ ] **Step 1: Failing tests:** P&L booked per closing-fill date (scale out Mon/Tue; period "today" on Tue counts only Tue's part in net_pnl, trade counted once in Tue's stats); open trades excluded from counts but counted in open_trades; win rate ignores breakeven; breakdown by mistake sums P&L; time-of-day bucket for a 9:45 entry; pass reasons row counts; `daily_realised_pnl` includes fees only for trades closed today.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(journal): summarise trades and passes for a period`.

### Task 7: Routes, settings, export, scheduler, docs

**Files:**
- Create: `backend/app/routes/journal.py`, `backend/app/journal/service.py`, `backend/app/journal/export.py`, `docs/decisions/0005-save-journal-bars-per-stock-day.md`
- Modify: `backend/app/schemas.py`, `backend/app/main.py`, `backend/app/user_settings.py`, `backend/app/routes/settings.py`, `backend/app/watchlist/scheduler.py`, `README.md`
- Test: `backend/tests/test_journal_routes.py`, `backend/tests/test_journal_export.py`, `backend/tests/test_settings_routes.py`, `backend/tests/test_scheduler.py`

**Interfaces:**
- `service.py` (glue between store, bars, snapshot, review; takes `fetch_bars_fn` and `get_quote_fn` as arguments):
  - `build_new_entry(conn, draft: EntryDraft, now, fetch_bars_fn, quote_fn) -> NewEntry` — fills `decided_at` (first fill time; pass: now or given time), setup snapshot via `get_setup_record` + `setup_values_at(decided_at)`, stock facts via `stock_facts_at` (trade price = first fill price; pass price = last bar ≤ pass time), quote from cache-or-fetch (failure → empty facts).
  - `review_trade(conn, entry) -> ReviewedTrade`, `score_saved_pass(conn, entry) -> ScoredPass`.
- Schemas (pydantic, `extra="forbid"` on inputs): `FillIn(side: Literal, time: AwareDatetime, price: confloat(gt=0, le=100000), shares: conint(ge=1, le=10_000_000))`; `TradeIn(kind: Literal["trade"], ticker, direction, setup_record_id: int | None, plan_stop, plan_target: float|None (gt 0), fees: confloat(ge=0, le=10000)=0, mistakes: list[str] (max 10), note: constr(max_length=1000)="", fills: list[FillIn] (1–50))`; `PassIn(kind: Literal["pass"], ticker, direction="long", setup_record_id, reasons: list[str] (1–20), note, decided_at: AwareDatetime | None)`; `EntryIn = Annotated[TradeIn | PassIn, Field(discriminator="kind")]`. Validators: reasons/mistakes ⊂ known keys; `other` needs a non-empty note; `followed_plan` alone; fills pass `validate_fills`; no fill in the future (422 with the message).
  - Out models mirror the dataclasses (`JournalEntryOut` with `figures`, `after_exit`, `plan_flags`, `pass_score`, `bar_warning: str | None`).
- Routes (`/api/journal`):
  - `GET /reasons` → `{pass_reasons: [{group, items:[{key,label}]}], mistakes: [{key,label}]}`
  - `GET /entries?kind=&period=` → list; `POST /entries` (201) → entry, saves bars (warning on failure); `GET /entries/{id}`; `PUT /entries/{id}`; `DELETE /entries/{id}` (204); 404 when missing.
  - `POST /preview` (body TradeIn) → `{figures, error: str | None}` without saving; validation failures of fills return `error` (200), not 422, so the panel can show them while typing.
  - `GET /entries/{id}/bars?interval=1m|5m` → `{bars, days: [{day, status}]}`; 5m built by aggregating 1m (`aggregate_bars(bars, minutes=5)` in `journal/bars.py`).
  - `GET /setups/{ticker}?day=YYYY-MM-DD&at=ISO` → setups for that day with values at `at` (picker).
  - `GET /open-trade/{ticker}` → entry or null.
  - `GET /summary?period=` → JournalSummary; `GET /daily-loss` → `{realised_pnl_today, max_daily_loss, level: "ok"|"warning"|"reached"}` (warning at ≥ 80% of limit).
  - `GET /export/entries.csv?period=`, `GET /export/fills.csv?period=` → `text/csv` with `Content-Disposition: attachment`.
- `export.py`: `entries_csv(trades, passes) -> str`, `fills_csv(entries) -> str`; `escape_cell(value: str) -> str` prefixes `'` when the cell starts with `=`, `+`, `-`, `@`, tab or CR.
- Settings: `GET/PUT /api/settings/journal` → `{risk_per_trade: float|None, max_position: float|None, max_daily_loss: float|None}` (each > 0 and ≤ 10,000,000 or null), stored in `app_meta` key `journal_settings` as JSON.
- Scheduler: `run_scheduled_bar_saving(db_path, now, fetch_bars_fn) -> int` called every loop tick (inside and outside the feeder window), errors logged, never raised.
- ADR 0005: why bars are stored per (ticker, day) in their own table rather than in `bar_cache` (cache is one row per ticker+interval and overwritten).
- README: Journal tab section, new routes, settings.
- [ ] **Step 1: Failing tests:** create trade (bars fetched via monkeypatched `get_bars`, setup snapshot uses history value at fill time), create pass, 422 for unknown reason / oversell / future fill / `other` without note, preview returns error text for oversell, Finviz failure still 201 with `bar_warning`, summary endpoint shape, daily-loss levels, CSV escaping and headers, journal settings round trip and rejection, scheduler tick calls bar saving outside the window and swallows errors with a log.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Full backend suite → PASS.
- [ ] **Step 5:** Commit `feat(journal): add journal API, settings, CSV export and bar saving job`.

### Task 8: Frontend API and chart support

**Files:**
- Create: `frontend/src/api/journal.ts`, `frontend/src/api/journal.test.ts`
- Modify: `frontend/src/api/settings.ts`, `frontend/src/components/CandleChart.tsx`, `frontend/src/components/CandleChart.test.tsx`

**Interfaces:**
- `api/journal.ts`: types mirroring Task 7 out models (`JournalEntry`, `TradeFigures`, `Fill`, `FillDraft`, `TradeDraft`, `PassDraft`, `JournalSummary`, `ReasonCatalog`, `DailyLoss`, `JournalPeriod`), and `fetchReasons`, `fetchEntries(kind?, period?)`, `fetchEntry(id)`, `createEntry(draft)`, `updateEntry(id, draft)`, `deleteEntry(id)`, `previewTrade(draft)`, `fetchEntryBars(id, interval)`, `fetchDaySetups(ticker, day, at)`, `fetchOpenTrade(ticker)`, `fetchSummary(period)`, `fetchDailyLoss()`, `exportUrl("entries"|"fills", period) -> string`.
- `api/settings.ts`: `JournalSettings`, `fetchJournalSettings`, `saveJournalSettings`.
- `CandleChart` new optional props: `markers?: ChartMarker[]` (`{time: string; side: "buy"|"sell"; shares: number; price: number}` → lightweight-charts markers: buy `belowBar` arrowUp up-colour, sell `aboveBar` arrowDown down-colour, text `B 500 @ 1.84`, size 1–3 by shares relative to the largest), `onBarClick?: (bar: Bar) => void` (subscribeClick, bar from the clicked time), `chartRef?: MutableRefObject<{ takeScreenshot: () => HTMLCanvasElement } | null>`.
- [ ] **Step 1: Failing tests:** markers passed to `candleSeries.setMarkers` sorted by time with labels; clicking calls `onBarClick` with the bar at that time; api functions call the right URLs/methods.
- [ ] **Step 2:** `cd frontend && npx vitest run` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `npx vitest run && npx tsc -b` → PASS.
- [ ] **Step 5:** Commit `feat(journal): add journal API client and chart markers and clicks`.

### Task 9: Log trade and Pass panels on the Stock page

**Files:**
- Create: `frontend/src/components/TradePanel.tsx`, `frontend/src/components/PassPanel.tsx`, `frontend/src/components/SetupPicker.tsx`, `frontend/src/components/DailyLossBanner.tsx`, `frontend/src/positionSize.ts` (+ tests for each: `TradePanel.test.tsx`, `PassPanel.test.tsx`, `positionSize.test.ts`, `DailyLossBanner.test.tsx`)
- Modify: `frontend/src/components/StockView.tsx` (+ test), `frontend/src/components/SetupsView.tsx` (banner), `frontend/src/styles.css`

**Interfaces:**
- `positionSize.ts`: `suggestShares(riskPerTrade: number, entry: number, stop: number, maxPosition: number | null) -> number` = floor(risk ÷ |entry − stop|), capped by floor(maxPosition ÷ entry); 0 when entry = stop.
- `TradePanel` props: `{ticker, setups: DaySetup[], defaultSetupId: number|null, existing: JournalEntry|null, settings: JournalSettings, clickedBar: Bar|null, onSaved(entry), onClose()}`. Behaviour: direction toggle; plan stop/target prefilled from the chosen setup; fills table (side/time/price/shares) with "Add fill"; a `clickedBar` adds a fill (time = bar time, price = bar close, side = opening side for the first fill, closing side after); warning "Price is outside that candle's range" when edited price is outside low–high of the clicked bar; debounced (300 ms) `previewTrade` showing average entry/exit, shares held, money in, P&L $ and R, or the preview error; mistake chips; fees; note; position-size line when `risk_per_trade` is set; Save → `createEntry`/`updateEntry`; shows `bar_warning` after save.
- `PassPanel` props: `{ticker, setups, defaultSetupId, onSaved, onClose}`; grouped reason chips (multi-select), note (required when "Other"), Save disabled until one reason.
- `SetupPicker`: select of the day's setups (`pattern timeframe · state at that time · score · Sykes`) + "No setup".
- StockView: buttons "Log trade" (opens open trade if `fetchOpenTrade` returns one, with "Start a new trade instead") and "Pass" above the chart; `L`/`P`/`Esc` shortcuts ignored when focus is in input/textarea/select; while the trade panel is open, `onBarClick` feeds `clickedBar`; markers of this ticker's logged fills on the live chart; position-size line on each setup card (`Size 625 sh ($1,150) to risk $50`) when set; `DailyLossBanner` at the top.
- `DailyLossBanner`: fetches `fetchDailyLoss`; renders nothing at `ok`, amber "Close to max daily loss (−$170 of −$200)" at `warning`, red "Max daily loss reached (−$212 of −$200)" at `reached`.
- [ ] **Step 1: Failing tests:** `suggestShares(50, 1.84, 1.76, null) === 625`; capped by max position; pressing `L` opens the trade panel, `P` the pass panel, `Esc` closes, `L` inside an input does nothing; clicking a bar with the panel open adds a buy fill then a sell fill; preview error is shown; pass Save disabled until a reason picked and when "Other" lacks a note; banner levels render the right text.
- [ ] **Step 2:** Run vitest → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `npx vitest run && npx tsc -b` → PASS.
- [ ] **Step 5:** Commit `feat(journal): log trades and passes from the Stock page`.

### Task 10: Journal tab

**Files:**
- Create: `frontend/src/components/JournalView.tsx`, `JournalSummaryPanel.tsx`, `PnlChart.tsx`, `JournalEntryDetail.tsx`, `JournalSettingsPanel.tsx` (+ `JournalView.test.tsx`, `JournalEntryDetail.test.tsx`)
- Modify: `frontend/src/App.tsx` (+ `App.test.tsx`), `frontend/src/styles.css`, `README.md`

**Interfaces:**
- Tab order: `["Setups", "Screens", "Watchlist", "Stock", "Journal", "Track record"]`.
- JournalView: period filter (Today / This week / This month / All time, default This week), DailyLossBanner, summary tiles, `PnlChart` (lightweight-charts line of cumulative + histogram of per-trade P&L), breakdown tables (country, industry, pattern, mistakes, time of day, duration, pass reasons, you vs. the system), entries list with Trades / Passes / Both filter, Export buttons (links to `exportUrl`), settings panel (risk per trade, max position, max daily loss).
- JournalEntryDetail: saved chart (1m/5m toggle) with markers and plan stop/target lines, missing/partial day notices (`Bars for Oct 3 are no longer available from Finviz.`), plan flags, after-exit line ("Kept going +1.4R after you sold" / "Dropped 2.0R after you sold"), fills table, Edit (opens TradePanel/PassPanel with `existing`), Delete with confirm, Save as image (download PNG via `takeScreenshot().toDataURL()`).
- [ ] **Step 1: Failing tests:** Journal tab renders and lists entries from a mocked API; period change refetches summary; trade row shows P&L and R; clicking a row opens detail with fills; delete asks to confirm; missing-day notice shown.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `npx vitest run && npx tsc -b`, full backend suite → PASS. Browser check with Playwright: log a trade on a real ticker via the UI, see it in the Journal tab, open its chart, delete it.
- [ ] **Step 5:** Commit `feat(journal): add the Journal tab`; memory-bank update as its own `docs(memory-bank): ...` commit.
