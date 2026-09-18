from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from app.cache import get_cached_quote, set_cached_quote
from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import get_quote
from app.schemas import QuoteResponse

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
    except FinvizAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    set_cached_quote(ticker, data)
    return QuoteResponse(**data)


@router.get("/{ticker}/refresh", response_model=QuoteResponse)
def refresh_stock(ticker: TickerPath) -> QuoteResponse:
    return _fetch_quote(ticker, use_cache=False)


@router.get("/{ticker}", response_model=QuoteResponse)
def get_stock(ticker: TickerPath) -> QuoteResponse:
    return _fetch_quote(ticker, use_cache=True)
