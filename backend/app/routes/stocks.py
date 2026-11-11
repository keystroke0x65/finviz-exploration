import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.cache import get_cached_quote, set_cached_quote
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError, TickerNotFoundError
from app.finviz_client import get_news, get_quote
from app.news_cache import read_cached_news, write_cached_news
from app.routes.dependencies import finviz_error_to_http, get_db_connection
from app.schemas import NewsOut, QuoteResponse

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

# Real tickers are short, alphabetic (plus '.'/'-' for share classes like
# "BRK.B"); this bounds the blast radius of malformed input hitting the
# Finviz client and the cache, per the handling-external-input rule.
TICKER_PATTERN = r"^[A-Za-z.\-]{1,10}$"
TickerPath = Annotated[str, Path(pattern=TICKER_PATTERN)]


def _fetch_quote(ticker: str, *, use_cache: bool) -> QuoteResponse:
    ticker = ticker.upper()

    if use_cache:
        cached = get_cached_quote(ticker)
        if cached is not None:
            return QuoteResponse(**cached)

    try:
        data = get_quote(ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        raise finviz_error_to_http(exc) from exc

    set_cached_quote(ticker, data)
    return QuoteResponse(**data)


@router.get("/{ticker}/refresh", response_model=QuoteResponse)
def refresh_stock(ticker: TickerPath) -> QuoteResponse:
    return _fetch_quote(ticker, use_cache=False)


@router.get("/{ticker}", response_model=QuoteResponse)
def get_stock(ticker: TickerPath) -> QuoteResponse:
    return _fetch_quote(ticker, use_cache=True)


@router.get("/{ticker}/news", response_model=NewsOut)
def get_stock_news(
    ticker: TickerPath, conn: Annotated[sqlite3.Connection, Depends(get_db_connection)], refresh: bool = False
) -> NewsOut:
    """The stock's recent news, newest first; cached briefly, `refresh` asks Finviz again."""
    ticker = ticker.upper()
    now = datetime.now(timezone.utc)
    cached = None if refresh else read_cached_news(conn, ticker, now)
    if cached is not None:
        return NewsOut(items=[asdict(item) for item in cached])
    try:
        items = get_news(ticker)
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        raise finviz_error_to_http(exc) from exc
    write_cached_news(conn, ticker, items, now)
    return NewsOut(items=[asdict(item) for item in items])
