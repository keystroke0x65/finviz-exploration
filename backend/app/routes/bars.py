import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.bars.loader import load_bars
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import get_bars
from app.market_time import EASTERN
from app.patterns.indicators import session_levels, session_vwap
from app.patterns.levels import find_daily_levels
from app.routes.dependencies import finviz_error_to_http, get_db_connection
from app.routes.stocks import TickerPath
from app.schemas import BarsOut

router = APIRouter(prefix="/api/bars", tags=["bars"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


@router.get("/{ticker}", response_model=BarsOut)
def get_ticker_bars(
    ticker: TickerPath, conn: DbConnection, interval: Annotated[Literal["1m", "5m", "daily"], Query()] = "5m"
) -> BarsOut:
    ticker = ticker.upper()
    now = datetime.now(timezone.utc)
    try:
        daily = load_bars(conn, ticker, "daily", now, get_bars)
        series = daily if interval == "daily" else load_bars(conn, ticker, interval, now, get_bars)
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        raise finviz_error_to_http(exc) from exc

    is_intraday = interval != "daily"
    # Levels belong to the day the latest bars are from, so the chart still
    # shows the last session's levels after the close or over a weekend.
    session_day = (series.bars[-1].time if series.bars else now).astimezone(EASTERN).date()
    return BarsOut(
        bars=[asdict(bar) for bar in series.bars],
        fetched_at=series.fetched_at,
        daily_levels=[asdict(level) for level in find_daily_levels(daily.bars)],
        session=asdict(session_levels(series.bars, daily.bars, session_day)) if is_intraday else None,
        vwap=session_vwap(series.bars) if is_intraday else None,
    )
