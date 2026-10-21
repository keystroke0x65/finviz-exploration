"""Manual check that the Finviz Elite export API integration still works.

Not run in CI (hits the real Finviz API and requires a valid FINVIZ_API_TOKEN).
Run manually after Finviz changes something on their end, or when debugging
an unexpected error from the app.

Usage:
    cd backend && python -m scripts.finviz_sanity_check AAPL
    cd backend && python -m scripts.finviz_sanity_check --screens
"""

import argparse
import sys
from dataclasses import replace

from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import find_unrecognised_codes, get_quote, run_screen
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ticker", nargs="?", default="AAPL")
    parser.add_argument(
        "--screens", action="store_true", help="check default screens and every form/signal code"
    )
    args = parser.parse_args()

    is_ok = check_screens() if args.screens else check_quote(args.ticker)
    sys.exit(0 if is_ok else 1)


if __name__ == "__main__":
    main()
