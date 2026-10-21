"""Manual check that the Finviz Elite export API integration still works.

Not run in CI (hits the real Finviz API and requires a valid FINVIZ_API_TOKEN).
Run manually after Finviz changes something on their end, or when debugging
an unexpected error from the app.

Usage:
    cd backend && python -m scripts.finviz_sanity_check AAPL
    cd backend && python -m scripts.finviz_sanity_check --screens
    cd backend && python -m scripts.finviz_sanity_check --bars HOST
"""

import argparse
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.errors import FinvizAuthError, TickerNotFoundError
from app.db import connect
from app.finviz_client import find_unrecognised_codes, get_bars, get_quote, run_screen
from app.market_time import EASTERN
from app.scanning.scanner import finviz_scan_deps, scan_ticker
from app.scanning.verdicts import read_verdicts
from app.setups.store import list_current_setups
from app.screens.filter_form import FORM_OPTIONS, SIGNAL_OPTIONS, ScreenForm, form_to_codes
from app.screens.store import DEFAULT_SCREENS


def check_quote(ticker: str) -> bool:
    print(f"Fetching live Finviz quote for {ticker}...")
    try:
        data = get_quote(ticker)
    except (TickerNotFoundError, FinvizAuthError) as exc:
        print(f"FAIL: {exc}")
        return False

    print("OK. Sample fields:")
    for key in ("Ticker", "Company", "Price", "Sector"):
        print(f"  {key}: {data.get(key)}")
    return True


def check_screens() -> bool:
    print("Running default screens...")
    for screen in DEFAULT_SCREENS:
        criteria = screen.criteria
        result = run_screen(criteria.filters, criteria.signal, criteria.order)
        print(f"  {screen.name}: {len(result.rows)} rows")

    # Finviz silently ignores codes it doesn't know, so the form's codes are
    # only trustworthy if each one narrows the whole-market result.
    form_codes = [
        form_to_codes(replace(ScreenForm(), **{field_name: option}))[0]
        for field_name, options in FORM_OPTIONS.items()
        for option in options
    ]
    print(f"Checking {len(form_codes)} form codes and {len(SIGNAL_OPTIONS)} signals...")
    unrecognised = find_unrecognised_codes(form_codes, None)
    for signal in SIGNAL_OPTIONS:
        unrecognised += find_unrecognised_codes([], signal)

    if unrecognised:
        print(f"FAIL: Finviz ignores: {', '.join(unrecognised)}")
        return False
    print("PASS: Finviz recognises every form code and signal.")
    return True


# Intraday bars should be from today or, after a weekend/holiday, a recent day.
MAX_INTRADAY_AGE_DAYS = 4


def check_bars(ticker: str) -> bool:
    print(f"Fetching live Finviz bars for {ticker}...")
    all_ok = True
    for interval in ("daily", "5m", "1m"):
        bars = get_bars(ticker, interval)
        if not bars:
            print(f"  FAIL {interval}: no bars")
            all_ok = False
            continue
        first, last = bars[0].time.astimezone(EASTERN), bars[-1].time.astimezone(EASTERN)
        print(f"  {interval}: {len(bars)} bars, {first:%Y-%m-%d %H:%M} to {last:%Y-%m-%d %H:%M} ET")
        if interval != "daily" and datetime.now(EASTERN) - last > timedelta(days=MAX_INTRADAY_AGE_DAYS):
            print(f"  FAIL {interval}: latest bar is older than {MAX_INTRADAY_AGE_DAYS} days")
            all_ok = False

    print("Running a full scan of the ticker against a temporary database...")
    with tempfile.TemporaryDirectory() as folder:
        conn = connect(str(Path(folder) / "sanity.db"))
        found = scan_ticker(conn, ticker, None, datetime.now(timezone.utc), finviz_scan_deps())
        for setup in list_current_setups(conn, ticker):
            print(
                f"  {setup.direction:5} {setup.pattern:24} {setup.timeframe:5} {setup.state:10} "
                f"entry {setup.entry} stop {setup.stop} target {setup.capped_target} "
                f"({setup.available_reward_risk:.1f}R) score {setup.score}"
            )
        verdict, _ = read_verdicts(conn)[ticker]
        print(f"Verdict: {verdict.call} (score {verdict.score})")
        for reason in verdict.reasons:
            print(f"  - {reason}")
        conn.close()
    print(f"{found} setups recorded.")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ticker", nargs="?", default="AAPL")
    parser.add_argument(
        "--screens", action="store_true", help="check default screens and every form/signal code"
    )
    parser.add_argument("--bars", action="store_true", help="fetch 1m/5m/daily bars and scan the ticker")
    args = parser.parse_args()

    if args.screens:
        is_ok = check_screens()
    elif args.bars:
        is_ok = check_bars(args.ticker.upper())
    else:
        is_ok = check_quote(args.ticker)
    sys.exit(0 if is_ok else 1)


if __name__ == "__main__":
    main()
