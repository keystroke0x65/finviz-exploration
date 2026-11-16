# Setup Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Log trade / Pass setup picker offers the setups that fit the trade, best first.

**Architecture:** A pure matching function in `backend/app/journal/setup_matching.py`; the day-setups route returns `{matches, others}`; the panels fetch their own setups from their first fill (trade) or the pass moment.

**Tech Stack:** FastAPI, pydantic; React + TypeScript, vitest.

**Spec:** `docs/superpowers/specs/2026-11-16-setup-picker-design.md`

## Global Constraints
- Direction filter only when a direction is given (trades); passes get any direction.
- Dedupe key: (pattern, timeframe, direction, entry); keep the latest detected at or before the moment.
- Rank: |entry − price| ÷ price, then |triggered_at − moment| (no trigger last), then score descending.

## Review Focus
1. Logging the next day for a trade entered yesterday → setups of the entry's day, not today's.
2. No fills yet → matches at "now".
3. A setup detected after the entry → only under "Other".
4. A setup stopped out before the entry → only under "Other".
5. Editing a saved trade keeps its saved setup selected even if it no longer ranks first.

---

### Task 1: Matching function and route
**Files:** Create `backend/app/journal/setup_matching.py` (+ `tests/test_journal_setup_matching.py`); modify `backend/app/routes/journal.py`, `backend/app/journal/schemas.py`, `tests/test_journal_routes.py`, README.
**Produces:** `match_setups(records: list[SetupRecord], moment: datetime, direction: Direction | None, price: float | None) -> tuple[list[SetupRecord], list[SetupRecord]]`; route `GET /api/journal/setups/{ticker}?day&at&direction&price` → `DaySetupsOut{matches: DaySetupOut[], others: DaySetupOut[]}`; `DaySetupOut` gains `triggered_at`, `detected_at`.
- [ ] failing tests: filters direction; excludes later-detected and earlier-resolved; dedupes copies; ranks by entry closeness then trigger time then score; route returns matches/others with values at the moment.
- [ ] implement; backend suite green; commit `feat(journal): match a trade's setups by direction, time and price`.

### Task 2: Panels use the matches
**Files:** `frontend/src/api/journal.ts`, `SetupPicker.tsx`, `TradePanel.tsx`, `PassPanel.tsx`, `StockView.tsx`, `JournalEntryDetail.tsx` (+ tests).
**Interfaces:** `fetchDaySetups(ticker, day, at, direction?, price?) -> Promise<DaySetups>`; `SetupPicker({matches, others, ticker, selectedId, onChange, matchLabel})` renders two optgroups; TradePanel fetches setups itself from the first fill (debounced 400 ms) or now, pre-selects the preferred id if it is a match else the top match, never overriding a user's own choice or an existing entry's setup.
- [ ] failing tests: optgroup labels and option text; TradePanel re-fetches with the first fill's day/time/direction/price and pre-selects the top match; keeps a manual choice; PassPanel fetches at now with no direction.
- [ ] implement; vitest + tsc green; browser check; commit `feat(journal): offer the setups that fit the trade first`.
