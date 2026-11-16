# Setup picker: best matches for the trade

Date: 2026-11-16
Status: approved in chat ("okay cool ... build the picker stuff")

## Intent
Logging a trade minutes (or a day) after it, the user couldn't tell which of a stock's
setups they traded: the picker listed every setup of the day (RAIN: 49), including
re-detections, shorts on a long trade, and setups that appeared after the entry or had
already stopped out. The picker should offer the few setups that fit the trade, best first.

## Goals
- Matches: same direction as the trade; detected at or before the entry; not resolved
  (stop / target / expired) before the entry. Copies of one setup (same pattern, timeframe,
  direction, entry) shown once.
- Ranked by closeness of the setup's entry to the first fill's price, then by how close its
  trigger time is to the entry time, then by score. The best match is pre-selected unless the
  user picked another (or the Stock page's selected setup is a match).
- Labels: pattern, timeframe, entry price, trigger time (or "forming"), score, Sykes grade.
- The list follows the fills: re-fetched when the first fill's time or price changes.
- The rest of the day's setups stay reachable under "Other <TICKER> setups today (N)".
- Passing: same rules at the moment of the pass, any direction, ranked by score.

## Non-goals
- No daily reset or new store: setups are already kept permanently (setup_records +
  setup_history), and the track record depends on them.

## Approaches
- **Chosen: matching on the backend.** `GET /api/journal/setups/{ticker}` takes the entry time,
  direction and price and returns `{matches, others}`; a pure function does the matching so it
  is tested without a UI. Same API for the trade panel, the pass panel and editing.
- Filtering in the browser: the rules (live at a time, dedupe, ranking) are business logic
  and the browser lacks resolved_at; lost.

## Left to the builder
Exact label wording; how the panel debounces re-fetching.
