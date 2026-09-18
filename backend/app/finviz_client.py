import io

import pandas as pd
import requests

from app.config import get_settings
from app.errors import FinvizAuthError, TickerNotFoundError

# /export.ashx is a legacy alias that 301-redirects to /export/screener;
# /export/stock (a different endpoint) returns historical price bars, not
# a current quote row, so it doesn't apply here.
FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"

# Finviz's "Overview" screener view code, giving one row per ticker with
# Sector, Market Cap, P/E, Price, Change, Volume, etc.
QUOTE_VIEW = "111"


def get_quote(ticker: str) -> dict:
    settings = get_settings()
    response = requests.get(
        FINVIZ_EXPORT_URL,
        params={
            "v": QUOTE_VIEW,
            "t": ticker,
            "auth": settings.finviz_api_token,
        },
        timeout=10,
    )

    if response.status_code == 401:
        raise FinvizAuthError()
    response.raise_for_status()

    # dtype=str keeps every column as the raw Finviz string (e.g. "1.35%",
    # "3.45T"); default dtype inference produces a dict with inconsistent
    # value types per ticker, since only some columns are pure numbers.
    df = pd.read_csv(io.StringIO(response.text), dtype=str)
    if df.empty:
        raise TickerNotFoundError(ticker)

    row = df.iloc[0].to_dict()
    # pandas represents missing cells as float NaN even in a dtype=str frame,
    # and on pandas's newer "str" extension dtype (3.0+), DataFrame.where(...,
    # None) silently leaves those NaNs in place instead of casting them —
    # https://github.com/pandas-dev/pandas/issues/58484. json.dumps then
    # serializes NaN as a bare `NaN` token, which isn't valid JSON. Cleaning
    # the already-extracted row per-value with pd.isna() sidesteps the
    # dtype-cast quirk entirely.
    return {key: (None if pd.isna(value) else value) for key, value in row.items()}
