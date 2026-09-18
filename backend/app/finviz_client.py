import io

import pandas as pd
import requests

from app.config import get_settings
from app.errors import FinvizAuthError, TickerNotFoundError

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export.ashx"

# Finviz's quote export view code; "152" returns the overview column set
# (price, sector, market cap, P/E, etc.) used by the /api/stocks endpoint.
QUOTE_VIEW = "152"


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

    return df.iloc[0].to_dict()
