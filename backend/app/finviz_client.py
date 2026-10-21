import io
import threading
import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import requests

from app.config import get_settings
from app.errors import (
    FinvizAuthError,
    FinvizRateLimitError,
    FinvizUnavailableError,
    TickerNotFoundError,
)

# /export.ashx is a legacy alias that 301-redirects to /export/screener;
# /export/stock (a different endpoint) returns historical price bars, not
# a current quote row, so it doesn't apply here.
FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"

# Finviz's "Overview" screener view code, giving one row per ticker with
# Sector, Market Cap, P/E, Price, Change, Volume, etc.
QUOTE_VIEW = "111"

# Finviz's "Custom" view: returns exactly the column ids passed in `c`.
CUSTOM_VIEW = "152"

# Ticker, Company, Country, Market Cap, Shares Float, Average Volume,
# Relative Volume, Price, Change, Volume, After-Hours Close, After-Hours
# Change, News Time, News URL, News Title. Finviz returns them in id order
# whatever order is requested, so rows are read by header name.
SCREEN_COLUMN_IDS = "1,2,5,6,25,63,64,65,66,67,71,72,135,136,137"

# Ticker only: the cheapest export, used when just counting rows.
COUNT_COLUMN_IDS = "1"

MIN_SECONDS_BETWEEN_REQUESTS = 1.0
REQUEST_TIMEOUT_SECONDS = 10


class _RequestPacer:
    """Keeps at least `min_interval_seconds` between Finviz requests."""

    def __init__(
        self,
        min_interval_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None
        self._lock = threading.Lock()

    def wait_for_turn(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_request_at is not None:
                remaining = self._min_interval_seconds - (now - self._last_request_at)
                if remaining > 0:
                    self._sleep(remaining)
                    now += remaining
            self._last_request_at = now


# Module-level on purpose: Finviz has no documented rate limits and the whole
# process (routes + background feeder) shares one Elite account, so pacing
# has to be process-wide rather than per caller.
_request_pacer = _RequestPacer(MIN_SECONDS_BETWEEN_REQUESTS)


@dataclass(frozen=True)
class ScreenRow:
    ticker: str
    company: str | None
    country: str | None
    market_cap_millions: float | None
    float_millions: float | None
    average_volume_thousands: float | None
    relative_volume: float | None
    price: float | None
    change_percent: float | None
    volume: int | None
    after_hours_close: float | None
    after_hours_change_percent: float | None
    news_time: str | None
    news_url: str | None
    news_title: str | None


@dataclass(frozen=True)
class ScreenResult:
    rows: list[ScreenRow]


def _fetch_export_csv(params: dict[str, str], operation: str) -> str:
    settings = get_settings()
    _request_pacer.wait_for_turn()
    try:
        response = requests.get(
            FINVIZ_EXPORT_URL,
            params={**params, "auth": settings.finviz_api_token},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # requests' messages include the full URL, auth token and all, so the
        # original exception is deliberately not chained or echoed.
        raise FinvizUnavailableError(operation, type(exc).__name__) from None

    if response.status_code == 401:
        raise FinvizAuthError()
    if response.status_code == 429:
        raise FinvizRateLimitError(operation)
    if not response.ok:
        raise FinvizUnavailableError(operation, f"HTTP {response.status_code}")
    return response.text


UNEXPECTED_FORMAT = "unexpected response format"


def _read_csv_as_strings(csv_text: str, operation: str) -> pd.DataFrame:
    # Finviz sometimes answers 200 with an HTML page (maintenance, login) or
    # an empty body; a CSV without a Ticker column is never a real export.
    try:
        # dtype=str keeps every column as the raw Finviz string (e.g. "1.35%",
        # "3.45T"); default dtype inference produces a dict with inconsistent
        # value types per ticker, since only some columns are pure numbers.
        df = pd.read_csv(io.StringIO(csv_text), dtype=str)
    except (pd.errors.ParserError, pd.errors.EmptyDataError):
        raise FinvizUnavailableError(operation, UNEXPECTED_FORMAT) from None
    if "Ticker" not in df.columns:
        raise FinvizUnavailableError(operation, UNEXPECTED_FORMAT)
    return df


def _clean_missing(row: dict) -> dict:
    # pandas represents missing cells as float NaN even in a dtype=str frame,
    # and on pandas's newer "str" extension dtype (3.0+), DataFrame.where(...,
    # None) silently leaves those NaNs in place instead of casting them —
    # https://github.com/pandas-dev/pandas/issues/58484. json.dumps then
    # serializes NaN as a bare `NaN` token, which isn't valid JSON. Cleaning
    # the already-extracted row per-value with pd.isna() sidesteps the
    # dtype-cast quirk entirely.
    return {key: (None if pd.isna(value) else value) for key, value in row.items()}


def get_quote(ticker: str) -> dict:
    operation = f"quote {ticker}"
    df = _read_csv_as_strings(_fetch_export_csv({"v": QUOTE_VIEW, "t": ticker}, operation), operation)
    if df.empty:
        raise TickerNotFoundError(ticker)
    return _clean_missing(df.iloc[0].to_dict())


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    return float(raw.rstrip("%").replace(",", ""))


def _parse_integer(raw: str | None) -> int | None:
    number = _parse_number(raw)
    return None if number is None else int(number)


def _to_screen_row(row: dict) -> ScreenRow:
    return ScreenRow(
        ticker=row["Ticker"],
        company=row.get("Company"),
        country=row.get("Country"),
        market_cap_millions=_parse_number(row.get("Market Cap")),
        float_millions=_parse_number(row.get("Shares Float")),
        average_volume_thousands=_parse_number(row.get("Average Volume")),
        relative_volume=_parse_number(row.get("Relative Volume")),
        price=_parse_number(row.get("Price")),
        change_percent=_parse_number(row.get("Change")),
        volume=_parse_integer(row.get("Volume")),
        after_hours_close=_parse_number(row.get("After-Hours Close")),
        after_hours_change_percent=_parse_number(row.get("After-Hours Change")),
        news_time=row.get("News Time"),
        news_url=row.get("News URL"),
        news_title=row.get("News Title"),
    )


def _screen_params(
    columns: str, filters: list[str], signal: str | None, order: str | None
) -> dict[str, str]:
    params = {"v": CUSTOM_VIEW, "c": columns, "f": ",".join(filters)}
    if signal:
        params["s"] = signal
    if order:
        params["o"] = order
    return params


def run_screen(filters: list[str], signal: str | None, order: str | None) -> ScreenResult:
    params = _screen_params(SCREEN_COLUMN_IDS, filters, signal, order)
    df = _read_csv_as_strings(_fetch_export_csv(params, "screen"), "screen")
    try:
        rows = [_to_screen_row(_clean_missing(record)) for record in df.to_dict("records")]
    except ValueError:
        # A non-numeric value in a numeric column means the export changed shape.
        raise FinvizUnavailableError("screen", UNEXPECTED_FORMAT) from None
    return ScreenResult(rows=rows)


def _count_screen_rows(filters: list[str], signal: str | None) -> int:
    operation = "check filter codes"
    params = _screen_params(COUNT_COLUMN_IDS, filters, signal, None)
    return len(_read_csv_as_strings(_fetch_export_csv(params, operation), operation))


def find_unrecognised_codes(filters: list[str], signal: str | None) -> list[str]:
    """Return the codes Finviz ignores.

    Finviz drops filter and signal codes it doesn't recognise without any
    error and applies the rest, so a typo quietly widens a screen. A code is
    treated as unrecognised when, applied on its own, it doesn't narrow the
    whole-market result. One request per code plus one for the baseline.
    """
    if not filters and not signal:
        return []
    market_size = _count_screen_rows([], None)
    unrecognised = [code for code in filters if _count_screen_rows([code], None) >= market_size]
    if signal and _count_screen_rows([], signal) >= market_size:
        unrecognised.append(signal)
    return unrecognised
