# Scan Progress Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a live progress bar on the Setups tab while a full watchlist scan (manual or automatic) runs.

**Architecture:** An in-memory, thread-safe progress tracker in the backend, fed by `run_scan` through an optional reporter argument and started/finished by the two full-scan callers. A polling endpoint exposes it; the Setups tab polls it every 2 s.

**Tech Stack:** FastAPI, Python threading; React + TypeScript, vitest.

**Spec:** `docs/superpowers/specs/2026-11-16-scan-progress-design.md`

## Global Constraints

- Phases: `preparing`, `scanning`, `finishing`. Kinds: `manual`, `automatic`.
- Poll interval: 2 s.
- One-stock scans never touch the tracker.
- `finish()` runs even when the scan raises.
- Docs (README) in the same diff; TDD; no `any`.

## Review Focus

1. A scan that crashes mid-way → the bar must not stay on "running" forever (finish in `finally`).
2. A manual scan clicked while an automatic one runs (409) → the bar keeps showing the automatic scan.
3. The Setups tab opened mid-scan → the bar appears within one poll.
4. Polling stops when the Setups tab unmounts (no timers left running).
5. The progress endpoint failing (backend restarting) → no error banner; the bar hides until the next good poll.

---

### Task 1: Progress tracker and scanner reporting

**Files:**
- Create: `backend/app/scanning/progress.py`
- Modify: `backend/app/scanning/scanner.py` (`run_scan`)
- Test: `backend/tests/test_scan_progress.py`, `backend/tests/test_scanner.py`

**Interfaces:**
- Produces:
  - `ScanKind = Literal["manual", "automatic"]`, `ScanPhase = Literal["preparing", "scanning", "finishing"]`
  - `@dataclass(frozen=True) ScanProgress(kind: ScanKind, phase: ScanPhase, done: int, total: int, ticker: str | None, started_at: datetime)`
  - `class ProgressTracker`: `start(kind, started_at) -> None`, `set_phase(phase) -> None`, `set_total(total) -> None`, `begin_ticker(ticker, index) -> None` (done = index), `finish() -> None`, `snapshot() -> ScanProgress | None`; all guarded by a `threading.Lock`.
  - module-level `scan_progress = ProgressTracker()` (one per process, like `scan_lock`).
  - `run_scan(..., progress: ProgressTracker | None = None)`: `set_phase("preparing")` at start; after active tickers are chosen `set_total(len(tickers))` + `set_phase("scanning")`; before each ticker `begin_ticker(ticker, index)`; after the loop `begin_ticker(None-equivalent)`: set done = total, then `set_phase("finishing")` before `_resolve_inactive_tickers`.

- [ ] Step 1: failing tests — `test_tracker_reports_nothing_when_idle`, `test_tracker_tracks_phase_total_and_current_ticker` (start → preparing/0/0; set_total(3), set_phase scanning, begin_ticker("BBB", 1) → done 1, ticker BBB), `test_finish_clears_progress`; in test_scanner: `test_run_scan_reports_each_ticker_to_progress` (fake tracker records calls: phases in order preparing→scanning→finishing, total = number of active tickers, begin_ticker called once per ticker in order).
- [ ] Step 2: run → FAIL (module missing / unexpected keyword `progress`).
- [ ] Step 3: implement.
- [ ] Step 4: run backend suite → PASS.
- [ ] Step 5: commit `feat(setups): track how far a watchlist scan has got`.

### Task 2: Wire the tracker to both full scans and expose it

**Files:**
- Modify: `backend/app/routes/setups.py` (`post_scan`, new `get_scan_progress`), `backend/app/watchlist/scheduler.py` (`run_scheduled_scan`), `backend/app/schemas.py`, `README.md`
- Test: `backend/tests/test_setups_routes.py`, `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: Task 1's `scan_progress`, `ScanProgress`.
- Produces: `GET /api/scans/progress` → `ScanProgressOut{running: bool, kind, phase, done, total, ticker, started_at}` (all but `running` null when idle).

- [ ] Step 1: failing tests — progress endpoint idle → `{"running": false, ...nulls}`; while a (monkeypatched) `run_scan` runs, the endpoint shows `running: true, kind: "manual"` (call the endpoint from inside the fake run_scan); after a crashing manual scan the endpoint is idle again; a one-stock scan (`{"ticker": "HOST"}`) never sets running; scheduler `run_scheduled_scan` starts kind `automatic` and finishes even when the scan raises.
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement (`try/finally` around run_scan in both callers; only full scans start the tracker).
- [ ] Step 4: backend suite → PASS.
- [ ] Step 5: commit `feat(setups): report scan progress at /api/scans/progress`.

### Task 3: Progress bar on the Setups tab

**Files:**
- Create: `frontend/src/components/ScanProgressBar.tsx` (+ `.test.tsx`)
- Modify: `frontend/src/api/setups.ts` (`ScanProgress`, `fetchScanProgress`), `frontend/src/components/SetupsView.tsx` (+ test), `frontend/src/styles.css`

**Interfaces:**
- `fetchScanProgress(): Promise<ScanProgress>` (`/api/scans/progress`).
- `ScanProgressBar({progress}: {progress: ScanProgress})` renders `role="progressbar"` with `aria-valuenow={done}`, `aria-valuemax={total}`, label "Scanning watchlist" / "Automatic scan", text `12 of 40 stocks · HOST · started 9:41 AM`, or "Preparing…" / "Finishing…" for those phases.
- SetupsView: polls every 2000 ms (setInterval, cleared on unmount); shows the bar above the scan status line while `running`; when it changes from running to not running, reloads setups + scan status; poll errors are ignored (bar hidden).

- [ ] Step 1: failing tests — bar text for scanning / preparing / finishing and the aria values; SetupsView (fake timers): shows the bar when progress says running, hides it and refetches setups when it stops, clears the interval on unmount, hides the bar when a poll fails.
- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement; the "Scan watchlist" button text becomes "Scanning…" while its own request runs.
- [ ] Step 4: `npx vitest run && npx tsc -b` → PASS; browser check with a real scan.
- [ ] Step 5: commit `feat(setups): show a progress bar while the watchlist scans`.
