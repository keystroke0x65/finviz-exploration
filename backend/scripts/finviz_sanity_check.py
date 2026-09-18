"""Manual check that the Finviz Elite export API integration still works.

Not run in CI (hits the real Finviz API and requires a valid FINVIZ_API_TOKEN).
Run manually after Finviz changes something on their end, or when debugging
an unexpected TickerNotFoundError/FinvizAuthError in production use.

Usage:
    cd backend && python -m scripts.finviz_sanity_check AAPL
"""

import sys

from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import get_quote


def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Fetching live Finviz quote for {ticker}...")

    try:
        data = get_quote(ticker)
    except TickerNotFoundError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    except FinvizAuthError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    print("OK. Sample fields:")
    for key in ("Ticker", "Company", "Price", "Sector"):
        print(f"  {key}: {data.get(key)}")


if __name__ == "__main__":
    main()
