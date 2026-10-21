# Phase 2 Milestone 1 — Screens + Watchlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Saved, editable Finviz screens (URL paste + form) that run on demand, and a
watchlist fed automatically from a "feeder" screen with 90-day retention, pinning, manual
add/remove, and per-day appearance history.

**Architecture:** Extends the Phase 1 FastAPI backend. `finviz_client` stays the only
module that knows Finviz URLs, codes and CSV. New pure modules (`screens/filter_form.py`,
`screens/finviz_url.py`, `watchlist/feeder.py`) hold the rules; `*/store.py` modules hold
SQLite access and take a `sqlite3.Connection` argument; routes wire them together. A
single asyncio background task started in FastAPI's lifespan runs the feeder. The React
frontend gains Screens and Watchlist views behind simple tab state (no router).

**Tech Stack:** Python 3.12, FastAPI, pandas, requests, pydantic-settings, SQLite,
pytest + responses; React 18 + TypeScript + Vite, Vitest + Testing Library. New
dependency: `tzdata` (Python) so `zoneinfo.ZoneInfo("America/New_York")` works in the
slim Docker image.

**Spec:** `docs/superpowers/specs/2026-10-20-screener-watchlist-patterns-design.md`
(sections "Data sources", "1. Screens", "2. Watchlist", "Architecture", "Errors",
"Testing", milestone 1 of "Delivery order").

## Global Constraints

- Follow `.claude/rules/*.md` (naming, error handling, external input, layering, tests).
- Finviz token only from `FINVIZ_API_TOKEN`; never logged, never in error messages or
  API responses.
- All Finviz requests go through `finviz_client`, paced at **no more than 1 request per
  second** process-wide.
- Screens are stored as raw Finviz codes (`filters` list, `signal`, `order`).
- A screen result with **more than 5,000 rows** is flagged `is_possibly_unfiltered`.
- Feeder window: **weekdays, 04:00 ≤ time < 20:00 America/New_York**; default interval
  **15 minutes**.
- Retention: auto entries expire **90 days** after `last_seen_in_feeder_at`; manual and
  pinned entries never expire.
- Removing an entry deletes it (and its appearances); a later feeder hit re-adds it as
  `auto`.
- Tickers: Phase 1 pattern `^[A-Za-z.\-]{1,10}$`, uppercased before storage.
- Wide-column export: `GET https://elite.finviz.com/export/screener?v=152&c=<ids>&f=…&s=…&o=…&auth=…`.
  Map columns by header name (Finviz returns them in id order).
- Units: Market Cap and Shares Float in millions; Average Volume in thousands.

## Review Focus

1. A typo'd or unsupported filter code: Finviz silently returns the whole market;
   the user must see "filters may have been ignored", not 10,000 rows as if valid
   (Task 1 test `test_run_screen_flags_result_over_threshold`; Task 10 sanity check).
2. Feeder runs near the window edges and across DST: 03:59 / 04:00 / 19:59 / 20:00 ET,
   weekends, and the November DST change day must behave by ET wall-clock time (Task 5
   test `test_feeder_window_edges`).
3. The same ticker hit repeatedly (every 15 min, or by two feeder screens in one run)
   must give one watchlist entry and at most one appearance per ticker per screen per
   ET day (Task 4 test `test_feeder_hit_twice_same_day_keeps_one_appearance`).
4. One feeder screen failing (auth, 429, timeout) must not stop other feeder screens or
   kill the background loop; the failure is reported (Task 5 test
   `test_run_feeder_continues_after_screen_failure`; Task 6 test
   `test_scheduler_tick_survives_feeder_exception`).
5. A pasted URL that isn't a Finviz screener URL, or is huge, must be rejected with a
   clear 422, not stored as junk (Task 2 tests `test_parse_rejects_non_finviz_host`,
   `test_parse_rejects_oversized_url`).

---

## File Structure

Backend (`backend/`):
- Modify `app/errors.py`: add `FinvizRateLimitError`, `FinvizUnavailableError`.
- Modify `app/finviz_client.py`: add `run_screen`, `ScreenRow`, request pacer.
- Create `app/screens/__init__.py`, `app/screens/filter_form.py` (form ↔ codes),
  `app/screens/finviz_url.py` (URL parse/build), `app/screens/store.py` (SQLite CRUD + seed).
- Create `app/db.py`: `connect(db_path) -> sqlite3.Connection`, creates all Milestone 1 tables.
- Create `app/watchlist/__init__.py`, `app/watchlist/store.py`, `app/watchlist/feeder.py`,
  `app/watchlist/scheduler.py`.
- Create `app/routes/screens.py`, `app/routes/watchlist.py`.
- Modify `app/main.py` (routers + lifespan), `app/config.py` (new settings),
  `app/schemas.py` (API models), `pyproject.toml` (`tzdata`).
- Tests: `tests/test_finviz_screen.py`, `tests/test_filter_form.py`,
  `tests/test_finviz_url.py`, `tests/test_screens_store.py`, `tests/test_screens_routes.py`,
  `tests/test_watchlist_store.py`, `tests/test_feeder.py`, `tests/test_scheduler.py`,
  `tests/test_watchlist_routes.py`, shared fixture in `tests/conftest.py`.
- Modify `scripts/finviz_sanity_check.py`.

Frontend (`frontend/src/`):
- Create `api/http.ts` (`requestJson`), `api/screens.ts`, `api/watchlist.ts`.
- Modify `api/stocks.ts` to use `requestJson`.
- Create `components/ScreensView.tsx`, `components/ScreenEditor.tsx`,
  `components/ScreenResultsTable.tsx`, `components/WatchlistView.tsx`, with `*.test.tsx`.
- Modify `App.tsx` (tabs: Screens, Watchlist, Lookup).

Docs: `README.md`, `.env.example`, `docs/decisions/0001-in-process-feeder-scheduler.md`,
`docs/decisions/0002-store-screens-as-raw-finviz-codes.md`.

---

### Task 1: Finviz screen export in the client

**Files:**
- Modify: `backend/app/errors.py`, `backend/app/finviz_client.py`
- Test: `backend/tests/test_finviz_screen.py`

**Interfaces:**
- Produces:
  - `class FinvizRateLimitError(Exception)` (HTTP 429), `class FinvizUnavailableError(Exception)`
    (timeout / connection error / 5xx; message names the operation, never the token).
  - `@dataclass(frozen=True) class ScreenRow`: `ticker: str`, `company: str | None`,
    `country: str | None`, `market_cap_millions: float | None`, `float_millions: float | None`,
    `average_volume_thousands: float | None`, `relative_volume: float | None`,
    `price: float | None`, `change_percent: float | None`, `volume: int | None`,
    `after_hours_close: float | None`, `after_hours_change_percent: float | None`,
    `news_time: str | None`, `news_url: str | None`, `news_title: str | None`.
  - `@dataclass(frozen=True) class ScreenResult`: `rows: list[ScreenRow]`,
    `is_possibly_unfiltered: bool`.
  - `def run_screen(filters: list[str], signal: str | None, order: str | None) -> ScreenResult`
  - Constants: `SCREEN_COLUMN_IDS = "1,2,5,6,25,63,64,65,66,67,71,72,135,136,137"`,
    `UNFILTERED_ROW_THRESHOLD = 5000`, `MIN_SECONDS_BETWEEN_REQUESTS = 1.0`.

- [ ] **Step 1: Write failing tests** (use `responses` like `test_finviz_client.py`; set
  `FINVIZ_API_TOKEN` and clear `get_settings` cache)

```python
SCREEN_CSV = (
    "Ticker,Company,Country,Market Cap,Shares Float,Average Volume,Relative Volume,Price,"
    "Change,Volume,After-Hours Close,After-Hours Change,News Time,News URL,News Title\n"
    "HOST,Host Digital Inc,USA,79.80,5.46,433.04,14.22,2.83,47.40%,6158186,2.73,-3.53%,"
    "2026-10-20 10:36:03,https://elite.finviz.com/news/1,Buyback\n"
    "NOAH,Noah Co,USA,12.00,,,,1.10,,,,,,,\n"
)

def test_run_screen_parses_typed_rows(): ...
    # result.rows[0] == ScreenRow(ticker="HOST", ..., change_percent=47.40,
    #   after_hours_change_percent=-3.53, volume=6158186, float_millions=5.46, ...)
    # result.rows[1].float_millions is None and change_percent is None
    # result.is_possibly_unfiltered is False

def test_run_screen_sends_codes_and_columns():
    # request query has v=152, c=SCREEN_COLUMN_IDS, f="geo_usa,sh_price_u20",
    # s="ta_topgainers", o="-change", auth="test-token"

def test_run_screen_omits_signal_and_order_when_none():  # no "s"/"o" in query

def test_run_screen_returns_empty_rows_for_header_only_csv():  # rows == [], no exception

def test_run_screen_flags_result_over_threshold():  # 5001 data rows -> True; 5000 -> False

def test_run_screen_raises_rate_limit_error_on_429():

def test_run_screen_raises_unavailable_on_timeout():  # responses body=requests.Timeout()

def test_run_screen_error_messages_never_contain_token():  # str(exc) for 401/429/timeout

def test_requests_are_paced(monkeypatch):
    # patch the pacer's clock/sleep; two run_screen calls 0.2s apart -> sleep(~0.8) called
```

- [ ] **Step 2: Run** `cd backend && pytest tests/test_finviz_screen.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement.** In `finviz_client.py` reuse `FINVIZ_EXPORT_URL`
  (`https://elite.finviz.com/export/screener`). Parse with `pd.read_csv(..., dtype=str)` as
  `get_quote` does, then map by header name. Percent → strip `%` → float; blank/NaN → None.
  Add a small `_RequestPacer` with an injectable `clock`/`sleep` and one module-level
  instance used by both `get_quote` and `run_screen`; comment why it is module-level
  (Finviz has no documented limits; one Elite account shared by the whole process).
  Map 429 → `FinvizRateLimitError`, `requests.Timeout`/`ConnectionError`/5xx →
  `FinvizUnavailableError`, 401 → existing `FinvizAuthError`. Unlike `get_quote`, an empty
  result is not an error.

- [ ] **Step 4: Run** `pytest -v` → all pass (including Phase 1 tests).

- [ ] **Step 5: Commit** `feat(finviz): add typed screen export with pacing and error types`

---

### Task 2: Filter form mapping and Finviz URL parsing (pure)

**Files:**
- Create: `backend/app/screens/__init__.py`, `backend/app/screens/filter_form.py`,
  `backend/app/screens/finviz_url.py`
- Test: `backend/tests/test_filter_form.py`, `backend/tests/test_finviz_url.py`

**Interfaces:**
- Produces (`filter_form.py`):
  - `@dataclass(frozen=True) class ScreenForm`: `country: Literal["usa"] | None = None`,
    `price_under: float | None = None`, `float_under_millions: float | None = None`,
    `market_cap: Literal["large_and_under","mid_and_under","small_and_under","micro_and_under","nano"] | None = None`,
    `volume_over_thousands: int | None = None`, `relative_volume_over: float | None = None`.
  - `FORM_OPTIONS: dict[str, list]` — allowed values per field:
    price_under `[1,2,3,4,5,7,10,15,20,30,40,50]`; float_under_millions `[1,5,10,20,50,100]`;
    volume_over_thousands `[100,200,500,1000,2000,5000,10000]`;
    relative_volume_over `[1,1.5,2,3,5,10]`; market_cap keys as above.
  - Code mapping: country `usa`→`geo_usa`; price `sh_price_u{n}`; float `sh_float_u{n}`;
    volume `sh_curvol_o{n}`; rel vol `sh_relvol_o{n}` (1.5 → `o1.5`, 2 → `o2`); market cap
    `cap_largeunder`, `cap_midunder`, `cap_smallunder`, `cap_microunder`, `cap_nano`.
  - `def form_to_codes(form: ScreenForm) -> list[str]`
  - `def codes_to_form(codes: list[str]) -> tuple[ScreenForm, list[str]]` — second item is
    the unknown codes, order preserved.
  - `class InvalidFormValueError(ValueError)` raised by `form_to_codes` for values not in
    `FORM_OPTIONS`.
  - `SIGNAL_OPTIONS = {"ta_topgainers": "Top gainers", "ta_toplosers": "Top losers",
    "ta_newhigh": "New high", "ta_unusualvolume": "Unusual volume", "ta_mostactive": "Most active"}`.
- Produces (`finviz_url.py`):
  - `@dataclass(frozen=True) class ScreenCriteria`: `filters: list[str]`, `signal: str | None`,
    `order: str | None`.
  - `def parse_finviz_screener_url(url: str) -> ScreenCriteria`
  - `def build_finviz_screener_url(criteria: ScreenCriteria) -> str` — returns
    `https://elite.finviz.com/screener.ashx?v=111&f=…[&s=…][&o=…]` (for "Open on Finviz").
  - `class InvalidScreenerUrlError(ValueError)`
  - `MAX_URL_LENGTH = 2000`, `MAX_FILTER_CODES = 50`, `CODE_PATTERN = r"^-?[a-z0-9_.]{1,40}$"`.

- [ ] **Step 1: Write failing tests**

```python
def test_form_to_codes_maps_user_screen():
    form = ScreenForm(country="usa", price_under=20, float_under_millions=10)
    assert form_to_codes(form) == ["geo_usa", "sh_price_u20", "sh_float_u10"]

def test_form_to_codes_formats_fractional_relative_volume():  # 1.5 -> "sh_relvol_o1.5"
def test_form_to_codes_rejects_value_not_in_options():  # price_under=17 -> InvalidFormValueError
def test_codes_to_form_round_trips_known_codes():
def test_codes_to_form_returns_unknown_codes_in_order():
    # ["geo_usa", "ta_rsi_os30", "sh_price_u20", "fa_pe_u10"] ->
    # (ScreenForm(country="usa", price_under=20), ["ta_rsi_os30", "fa_pe_u10"])

def test_parse_extracts_filters_signal_order():
    url = "https://elite.finviz.com/screener.ashx?v=111&f=geo_usa,sh_price_u20,sh_float_u10&s=ta_topgainers&o=-change"
    assert parse_finviz_screener_url(url) == ScreenCriteria(
        ["geo_usa", "sh_price_u20", "sh_float_u10"], "ta_topgainers", "-change")

def test_parse_accepts_finviz_com_without_elite():
def test_parse_handles_url_encoded_commas():  # f=geo_usa%2Csh_price_u20
def test_parse_returns_empty_filters_when_f_missing():
def test_parse_rejects_non_finviz_host():  # "https://evil.example/screener.ashx?f=geo_usa"
def test_parse_rejects_non_screener_path():  # finviz.com/quote.ashx?t=AAPL
def test_parse_rejects_oversized_url():  # len > MAX_URL_LENGTH
def test_parse_rejects_too_many_codes_or_bad_characters():
def test_build_url_round_trips_through_parse():
```

- [ ] **Step 2: Run** `pytest tests/test_filter_form.py tests/test_finviz_url.py -v` → FAIL.
- [ ] **Step 3: Implement** both modules with `urllib.parse`. Allowed hosts:
  `finviz.com`, `www.finviz.com`, `elite.finviz.com`; path `/screener.ashx`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(screens): map form fields and Finviz URLs to filter codes`

---

### Task 3: Database schema and screens store with seeding

**Files:**
- Create: `backend/app/db.py`, `backend/app/screens/store.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_screens_store.py`

**Interfaces:**
- Consumes: `ScreenCriteria` (Task 2).
- Produces:
  - `def connect(db_path: str) -> sqlite3.Connection` — `row_factory = sqlite3.Row`,
    `PRAGMA foreign_keys = ON`, creates (IF NOT EXISTS):
    `screens(id INTEGER PK, name TEXT NOT NULL, filters TEXT NOT NULL /* JSON list */, signal TEXT, sort_order TEXT, feeds_watchlist INTEGER NOT NULL, created_at TEXT, updated_at TEXT)`,
    `watchlist_entries(ticker TEXT PK, source TEXT CHECK(source IN ('auto','manual')), added_at TEXT, last_seen_in_feeder_at TEXT, is_pinned INTEGER NOT NULL DEFAULT 0)`,
    `watchlist_appearances(ticker TEXT REFERENCES watchlist_entries(ticker) ON DELETE CASCADE, seen_on TEXT, change_percent REAL, screen_id INTEGER, PRIMARY KEY(ticker, seen_on, screen_id))`,
    `app_meta(key TEXT PK, value TEXT)`. Timestamps are ISO-8601 UTC strings.
  - `@dataclass(frozen=True) class Screen`: `id: int`, `name: str`, `criteria: ScreenCriteria`,
    `feeds_watchlist: bool`, `created_at: datetime`, `updated_at: datetime`.
  - `@dataclass(frozen=True) class ScreenInput`: `name: str`, `criteria: ScreenCriteria`,
    `feeds_watchlist: bool`.
  - `create_screen(conn, screen_input, now: datetime) -> Screen`;
    `list_screens(conn) -> list[Screen]` (by id); `get_screen(conn, screen_id) -> Screen | None`;
    `update_screen(conn, screen_id, screen_input, now) -> Screen | None`;
    `delete_screen(conn, screen_id) -> bool`; `list_feeder_screens(conn) -> list[Screen]`;
    `seed_default_screens(conn, now) -> None`.
  - Seeds (only once, tracked by `app_meta` key `screens_seeded`):
    1. `"Top gainers — low float"`: filters `["geo_usa","sh_price_u20","sh_float_u10"]`,
       signal `"ta_topgainers"`, order `"-change"`, `feeds_watchlist=True`.
    2. `"After-hours"`: filters `["geo_usa","sh_price_u20","sh_float_u20","cap_largeunder"]`,
       signal None, order None, `feeds_watchlist=False`.
  - `conftest.py` fixture `db_conn(tmp_path)` → `connect(str(tmp_path / "test.db"))`, closed after.

- [ ] **Step 1: Write failing tests**

```python
def test_create_then_get_round_trips_criteria(db_conn): ...
def test_update_changes_fields_and_updated_at(db_conn): ...
def test_update_missing_screen_returns_none(db_conn): ...
def test_delete_returns_false_for_missing(db_conn): ...
def test_list_feeder_screens_only_returns_feeders(db_conn): ...
def test_seed_creates_two_default_screens(db_conn):
    seed_default_screens(db_conn, NOW)
    screens = list_screens(db_conn)
    assert [s.name for s in screens] == ["Top gainers — low float", "After-hours"]
    assert screens[0].feeds_watchlist and screens[0].criteria.signal == "ta_topgainers"
def test_seed_does_not_recreate_after_user_deletes_all(db_conn):
    seed_default_screens(db_conn, NOW); [delete_screen(db_conn, s.id) for s in list_screens(db_conn)]
    seed_default_screens(db_conn, NOW)
    assert list_screens(db_conn) == []
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(screens): add SQLite schema and screens store with default seeds`

---

### Task 4: Watchlist store with retention

**Files:**
- Create: `backend/app/watchlist/__init__.py`, `backend/app/watchlist/store.py`
- Test: `backend/tests/test_watchlist_store.py`

**Interfaces:**
- Consumes: `connect` (Task 3).
- Produces:
  - `@dataclass(frozen=True) class Appearance`: `seen_on: date`, `change_percent: float | None`, `screen_id: int`.
  - `@dataclass(frozen=True) class WatchlistEntry`: `ticker: str`,
    `source: Literal["auto","manual"]`, `added_at: datetime`,
    `last_seen_in_feeder_at: datetime | None`, `is_pinned: bool`,
    `appearances: list[Appearance]` (newest first).
  - `record_feeder_hit(conn, ticker, change_percent: float | None, screen_id: int, now: datetime) -> Literal["added","updated"]`
    — inserts as `auto` if absent; always sets `last_seen_in_feeder_at=now`; never changes a
    `manual` source; upserts the appearance for `(ticker, seen_on=ET date of now, screen_id)`
    with the latest change_percent.
  - `add_manual_entry(conn, ticker, now) -> WatchlistEntry` — inserts as `manual`, or
    converts an existing `auto` entry to `manual`.
  - `remove_entry(conn, ticker) -> bool`; `set_pinned(conn, ticker, is_pinned: bool) -> WatchlistEntry | None`;
    `list_entries(conn) -> list[WatchlistEntry]` ordered by `last_seen_in_feeder_at` desc
    (nulls last), then ticker; `get_entry(conn, ticker) -> WatchlistEntry | None`.
  - `expire_stale_entries(conn, now, retention_days: int) -> list[str]` — deletes `auto`,
    unpinned entries whose `last_seen_in_feeder_at` is older than `now - retention_days`;
    returns deleted tickers.
  - `EASTERN = ZoneInfo("America/New_York")` (add `tzdata>=2024.1` to `pyproject.toml`
    dependencies in this task).

- [ ] **Step 1: Write failing tests** (all `now` values are timezone-aware UTC)

```python
def test_feeder_hit_adds_auto_entry_with_appearance(db_conn): ...
def test_feeder_hit_twice_same_day_keeps_one_appearance(db_conn):
    # hits at 14:00Z and 18:00Z same ET day with change 10.0 then 25.0
    # -> one appearance, change_percent == 25.0, result of second call == "updated"
def test_feeder_hits_from_two_screens_same_day_keep_one_each(db_conn):
def test_appearance_date_uses_eastern_time(db_conn):
    # 2026-10-21T02:30Z is 2026-10-20 22:30 ET -> seen_on == date(2026, 10, 20)
def test_feeder_hit_keeps_manual_source(db_conn):
def test_manual_add_converts_auto_entry(db_conn):
def test_expire_removes_auto_entries_older_than_retention(db_conn):
    # last seen 91 days ago -> removed; 89 days ago -> kept
def test_expire_keeps_pinned_and_manual_entries(db_conn):
def test_remove_deletes_appearances_and_later_hit_re_adds_as_auto(db_conn):
def test_list_orders_by_last_seen_desc(db_conn):
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(watchlist): add watchlist store with ET-day appearances and retention`

---

### Task 5: Feeder logic

**Files:**
- Create: `backend/app/watchlist/feeder.py`
- Test: `backend/tests/test_feeder.py`

**Interfaces:**
- Consumes: `run_screen`, `ScreenResult`, error types (Task 1); `list_feeder_screens` (Task 3);
  `record_feeder_hit`, `expire_stale_entries`, `EASTERN` (Task 4).
- Produces:
  - `FEEDER_WINDOW_START = time(4, 0)`, `FEEDER_WINDOW_END = time(20, 0)`.
  - `def is_within_feeder_window(now: datetime) -> bool` — converts to ET; Mon–Fri;
    `start <= t < end`.
  - `@dataclass(frozen=True) class FeederResult`: `screens_run: int`, `tickers_added: list[str]`,
    `tickers_updated: list[str]`, `tickers_expired: list[str]`,
    `failed_screens: list[tuple[str, str]]` (screen name, user-facing reason).
  - `def run_feeder(conn, run_screen_fn: Callable[[list[str], str | None, str | None], ScreenResult], now: datetime, retention_days: int) -> FeederResult`
    — runs every feeder screen; catches `FinvizAuthError`, `FinvizRateLimitError`,
    `FinvizUnavailableError` per screen and records them in `failed_screens`; skips adding
    hits from a result with `is_possibly_unfiltered=True` and records it as failed with
    reason "filters may have been ignored"; runs `expire_stale_entries` once at the end.
    Does not check the window (callers decide).

- [ ] **Step 1: Write failing tests** (fake `run_screen_fn` returning canned `ScreenResult`s)

```python
@pytest.mark.parametrize("et_time, expected", [
    ("2026-10-20 03:59", False), ("2026-10-20 04:00", True),
    ("2026-10-20 19:59", True), ("2026-10-20 20:00", False),
    ("2026-10-24 10:00", False),  # Saturday
    ("2026-11-02 04:30", True),   # Monday after DST ends (Nov 1, 2026)
])
def test_feeder_window_edges(et_time, expected): ...  # build ET datetime, convert to UTC, assert

def test_run_feeder_adds_hits_from_feeder_screens_only(db_conn):
def test_run_feeder_continues_after_screen_failure(db_conn):
    # two feeder screens; first raises FinvizRateLimitError -> second still recorded,
    # failed_screens == [("First", <message mentioning rate limit>)]
def test_run_feeder_ignores_possibly_unfiltered_result(db_conn):
def test_run_feeder_expires_stale_entries(db_conn):
def test_run_feeder_with_no_feeder_screens_returns_empty_result(db_conn):
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(watchlist): add feeder that fills the watchlist from feeder screens`

---

### Task 6: Settings, background scheduler, and app lifespan

**Files:**
- Create: `backend/app/watchlist/scheduler.py`
- Modify: `backend/app/config.py`, `backend/app/main.py`, `.env.example`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `connect`, `seed_default_screens`, `run_feeder`, `is_within_feeder_window`, `run_screen`.
- Produces:
  - Settings: `feeder_interval_minutes: int = 15`, `watchlist_retention_days: int = 90`,
    `is_feeder_enabled: bool = True` (env `FEEDER_INTERVAL_MINUTES`,
    `WATCHLIST_RETENTION_DAYS`, `IS_FEEDER_ENABLED`). Add all three to `.env.example` with
    the defaults.
  - `def run_scheduled_feeder_tick(db_path: str, now: datetime, retention_days: int, run_screen_fn) -> FeederResult | None`
    — returns None outside the window; otherwise opens a connection, runs the feeder, logs
    a one-line summary (counts and failed screen names, no token), closes the connection.
    Any exception is logged with `logger.exception("feeder tick failed")` and returns None
    (the loop is the recovery point; comment why).
  - `async def feeder_loop(settings: Settings) -> None` — forever: `await asyncio.to_thread(run_scheduled_feeder_tick, …)`,
    then `await asyncio.sleep(settings.feeder_interval_minutes * 60)`.
  - `main.py` lifespan: `connect` + `seed_default_screens` once at startup; if
    `is_feeder_enabled`, start `feeder_loop` as a task and cancel it on shutdown.

- [ ] **Step 1: Write failing tests**

```python
def test_scheduler_tick_skips_outside_window(tmp_path):  # Saturday -> None, fake not called
def test_scheduler_tick_runs_feeder_inside_window(tmp_path):  # returns FeederResult
def test_scheduler_tick_survives_feeder_exception(tmp_path, caplog):
    # fake run_screen_fn raises RuntimeError -> returns None, "feeder tick failed" logged
def test_settings_read_feeder_env(monkeypatch):
def test_lifespan_seeds_default_screens(tmp_path, monkeypatch):
    # IS_FEEDER_ENABLED=false, DB_PATH=tmp; `with TestClient(app):` -> 2 screens in DB
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `pytest -v` → all PASS.
- [ ] **Step 5: Commit** `feat(watchlist): run feeder on a 15-minute background schedule`

---

### Task 7: Screens and watchlist API routes

**Files:**
- Create: `backend/app/routes/screens.py`, `backend/app/routes/watchlist.py`
- Modify: `backend/app/schemas.py`, `backend/app/main.py`
- Test: `backend/tests/test_screens_routes.py`, `backend/tests/test_watchlist_routes.py`

**Interfaces:**
- Consumes: everything above; Phase 1 `get_quote` and `TickerNotFoundError` for manual-add
  validation.
- Produces (Pydantic models in `schemas.py`; routes open a connection per request via a
  `get_db_connection` dependency using `get_settings().db_path`, so tests can override it):
  - `ScreenFormModel` mirrors `ScreenForm`; `ScreenIn {name: str (1–80, stripped), form: ScreenFormModel, extra_filters: list[str] (≤50, each matches CODE_PATTERN), signal: str | None (CODE_PATTERN), order: str | None (CODE_PATTERN), feeds_watchlist: bool = False}`.
  - `ScreenOut {id, name, form, extra_filters, signal, order, feeds_watchlist, finviz_url, created_at, updated_at}`.
  - `ScreenDraft {form, extra_filters, signal, order}`; `ParseUrlIn {url: str (≤2000)}`.
  - `ScreenRowOut` mirrors `ScreenRow`; `ScreenRunOut {rows: list[ScreenRowOut], is_possibly_unfiltered: bool, fetched_at: datetime}`.
  - `FormFieldsOut {options: dict[str, list], signals: dict[str, str]}`.
  - `AppearanceOut`, `WatchlistEntryOut` mirror the dataclasses; `AddTickerIn {ticker: str (Phase 1 pattern)}`; `PinIn {is_pinned: bool}`.
  - `FeederResultOut` mirrors `FeederResult` (failed_screens as `[{screen, reason}]`).
  - Routes:
    - `GET /api/screens` → `list[ScreenOut]`; `POST /api/screens` → 201; `PUT /api/screens/{screen_id}` → 200/404;
      `DELETE /api/screens/{screen_id}` → 204/404; `POST /api/screens/{screen_id}/run` → `ScreenRunOut`/404;
      `POST /api/screens/parse-url` → `ScreenDraft`/422; `GET /api/screens/form-fields` → `FormFieldsOut`.
    - `GET /api/watchlist`; `POST /api/watchlist` → 201 (404 if Finviz has no such ticker);
      `DELETE /api/watchlist/{ticker}` → 204/404; `PATCH /api/watchlist/{ticker}` → entry/404;
      `POST /api/watchlist/refresh` → `FeederResultOut` (runs feeder now, ignores window).
  - Error mapping (one helper used by both routers): `FinvizAuthError` → 502,
    `FinvizRateLimitError` → 503 "Finviz is rate limiting requests; try again in a minute",
    `FinvizUnavailableError` → 504, `InvalidFormValueError`/`InvalidScreenerUrlError` → 422.

- [ ] **Step 1: Write failing tests** (override `get_db_connection` with the `db_conn` fixture; patch `run_screen`/`get_quote` at the route module like Phase 1 tests)

```python
def test_create_screen_from_form_stores_codes_and_returns_finviz_url(): ...
    # POST {"name":"Mine","form":{"country":"usa","price_under":20},"extra_filters":["ta_rsi_os30"]}
    # -> 201; GET returns form + extra_filters; finviz_url contains "f=geo_usa,sh_price_u20,ta_rsi_os30"
def test_create_screen_rejects_form_value_not_in_options():  # price_under 17 -> 422
def test_create_screen_rejects_bad_extra_code():  # "geo usa; drop" -> 422
def test_parse_url_returns_draft_with_unknown_codes_as_extra():
def test_parse_url_rejects_non_finviz_url():  # 422
def test_run_screen_returns_rows_and_unfiltered_flag():
def test_run_missing_screen_returns_404():
def test_run_screen_maps_rate_limit_to_503():
def test_add_ticker_uppercases_and_validates_with_finviz():  # "host" -> "HOST", source manual
def test_add_unknown_ticker_returns_404():
def test_remove_missing_ticker_returns_404():
def test_pin_entry_sets_flag():
def test_refresh_runs_feeder_and_reports_failures():
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `pytest -v` → all PASS.
- [ ] **Step 5: Commit** `feat(api): add screens and watchlist routes`

---

### Task 8: Frontend API layer

**Files:**
- Create: `frontend/src/api/http.ts`, `frontend/src/api/screens.ts`, `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/api/stocks.ts`
- Test: `frontend/src/api/http.test.ts`, `frontend/src/api/screens.test.ts`; existing `stocks.test.ts` must still pass unchanged.

**Interfaces:**
- Produces:
  - `requestJson<T>(path: string, init?: RequestInit): Promise<T>` — moves Phase 1's error
    handling here (non-ok → `Error(body.detail ?? "Request failed (status)")`, tolerating
    non-JSON bodies); returns `undefined as T` for 204. `fetchQuote` calls it.
  - Types mirroring Task 7 models in camelCase-free form (keep backend snake_case field
    names to avoid a mapping layer): `ScreenForm`, `Screen`, `ScreenDraft`, `ScreenRow`,
    `ScreenRun`, `FormFields`, `WatchlistEntry`, `Appearance`, `FeederResult`.
  - `screens.ts`: `listScreens()`, `createScreen(input)`, `updateScreen(id, input)`,
    `deleteScreen(id)`, `runScreen(id)`, `parseScreenerUrl(url)`, `fetchFormFields()`.
  - `watchlist.ts`: `listWatchlist()`, `addToWatchlist(ticker)`, `removeFromWatchlist(ticker)`,
    `setPinned(ticker, isPinned)`, `refreshWatchlist()`.
  - JSON bodies sent with `Content-Type: application/json`; tickers `encodeURIComponent`-ed.

- [ ] **Step 1: Write failing tests** — `http.test.ts`: detail message, status fallback, 204
  returns undefined. `screens.test.ts`: `createScreen` sends POST with JSON body to
  `/api/screens`; `runScreen(3)` POSTs to `/api/screens/3/run`.
- [ ] **Step 2: Run** `cd frontend && npm test` → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `npx tsc -b` clean.
- [ ] **Step 5: Commit** `feat(frontend): add API clients for screens and watchlist`

---

### Task 9: Screens view

**Files:**
- Create: `frontend/src/components/ScreensView.tsx`, `ScreenEditor.tsx`, `ScreenResultsTable.tsx`
- Test: `frontend/src/components/ScreenEditor.test.tsx`, `ScreenResultsTable.test.tsx`

**Interfaces:**
- Consumes: Task 8 functions/types; `addToWatchlist`.
- Produces: `<ScreensView />` (no props), used by Task 10's `App`.
  - `ScreensView`: list of screens (name, "feeds watchlist" badge, Run / Edit / Delete,
    "Open on Finviz" link to `finviz_url`), "New screen" button, results table for the last run.
  - `ScreenEditor` props `{ initial: ScreenDraft & { name: string; feeds_watchlist: boolean } | null; formFields: FormFields; onSave(input): Promise<void>; onCancel(): void }`:
    URL paste box with "Import" (calls `parseScreenerUrl`, fills the form), selects for each
    form field from `formFields.options` (plus "Any"), signal select, extra codes shown as
    removable chips, feeds-watchlist checkbox, name input. Shows backend error detail on failure.
  - `ScreenResultsTable` props `{ run: ScreenRun; onAddToWatchlist(ticker): void }`: columns
    Ticker, Company, Price, Change %, AH Change %, Volume, Rel Vol, Float (M), Mkt Cap (M),
    News (title linking to `news_url`, `target="_blank" rel="noreferrer"`), actions
    (Open on Finviz `https://finviz.com/quote.ashx?t=<ticker>`, Add to watchlist). Shows a
    `role="alert"` warning "Finviz may have ignored some filters — check the screen's codes"
    when `is_possibly_unfiltered`. Empty `rows` → "No stocks match this screen right now."
    Null numbers render as "—". Shows "Fetched <local time>" from `fetched_at` above the
    table. (A per-row "Scan" action arrives in milestone 2.)

- [ ] **Step 1: Write failing tests**

```tsx
it("fills the form from a pasted Finviz URL")         // mock parseScreenerUrl; price select shows 20; extra chip "ta_rsi_os30"
it("shows backend error detail when save fails")
it("warns when the result may be unfiltered")         // role=alert text
it("shows an empty-state message when no rows")
it("renders missing numbers as a dash")
it("calls onAddToWatchlist with the row ticker")
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; `npx tsc -b` clean.
- [ ] **Step 5: Commit** `feat(frontend): add screens view with URL import and results table`

---

### Task 10: Watchlist view, navigation, sanity script, docs

**Files:**
- Create: `frontend/src/components/WatchlistView.tsx`, `WatchlistView.test.tsx`,
  `docs/decisions/0001-in-process-feeder-scheduler.md`,
  `docs/decisions/0002-store-screens-as-raw-finviz-codes.md`
- Modify: `frontend/src/App.tsx`, `backend/scripts/finviz_sanity_check.py`, `README.md`

**Interfaces:**
- Consumes: Task 8 watchlist functions; `ScreensView` (Task 9); Phase 1 `StockSearch`/`QuoteTable`.
- Produces:
  - `<WatchlistView />`: add-ticker form; "Refresh from feeder" button showing the
    `FeederResult` summary (added/updated/expired counts and any failed screens);
    table: Ticker (link to Finviz quote), Source (auto/manual), Added, Last seen, Pin toggle,
    Remove; expandable row showing appearances (date, change %). Auto entries show
    "expires <date>" (last seen + 90 days) unless pinned.
  - `App.tsx`: tab buttons "Screens" (default), "Watchlist", "Lookup" (Phase 1 search +
    quote table), state held in `App`.
  - Sanity script: new `--screens` mode that runs the two seed screens for real and, for
    every code `form_to_codes` can produce, checks the row count is below
    `UNFILTERED_ROW_THRESHOLD` (i.e. Finviz honoured it); prints PASS/FAIL per code, pacing
    via the client.
  - Decision records (format from `.claude/rules/making-an-architectural-decision.md`):
    0001 asyncio task in FastAPI lifespan vs APScheduler / OS cron (no new dependency, app
    is single-process and local; misses runs while Docker is down — accepted);
    0002 raw Finviz codes + form for a known subset vs a full typed filter model (hundreds
    of codes; user builds screens on Finviz and pastes URLs).
  - README: new features, new env vars, how the feeder schedule works, `--screens` sanity mode.

- [ ] **Step 1: Write failing tests** (`WatchlistView.test.tsx`)

```tsx
it("lists entries with source and last seen")
it("shows an expiry date for unpinned auto entries only")
it("toggles pin and re-renders the entry")
it("shows the backend error when adding an unknown ticker")
it("shows failed feeder screens after refresh")
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** view, tabs, sanity mode, docs.
- [ ] **Step 4: Verify**
  - `cd frontend && npm test && npx tsc -b` → all pass.
  - `cd backend && pytest -v` → all pass.
  - `docker compose up --build`, open http://localhost:5173: run "Top gainers — low float",
    add a row to the watchlist, click "Refresh from feeder", see entries appear.
  - `cd backend && FINVIZ_API_TOKEN=… python -m scripts.finviz_sanity_check --screens` → every code PASS.
- [ ] **Step 5: Commit** `feat(frontend): add watchlist view and tabs; docs and sanity checks for screens`
