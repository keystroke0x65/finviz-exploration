import sqlite3
from dataclasses import dataclass
from datetime import datetime, time
from typing import Callable

from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import ScreenResult
from app.screens.store import Screen, list_feeder_screens
from app.watchlist.store import EASTERN, expire_stale_entries, record_feeder_hit

# Pre-market opens at 04:00 ET and after-hours closes at 20:00 ET; outside
# that, top-gainer screens just repeat the last session.
FEEDER_WINDOW_START = time(4, 0)
FEEDER_WINDOW_END = time(20, 0)
SATURDAY = 5

RunScreenFunction = Callable[[list[str], str | None, str | None], ScreenResult]


@dataclass(frozen=True)
class FeederResult:
    screens_run: int
    tickers_added: list[str]
    tickers_updated: list[str]
    tickers_expired: list[str]
    failed_screens: list[tuple[str, str]]


def is_within_feeder_window(now: datetime) -> bool:
    eastern_now = now.astimezone(EASTERN)
    if eastern_now.weekday() >= SATURDAY:
        return False
    return FEEDER_WINDOW_START <= eastern_now.time() < FEEDER_WINDOW_END


def _fetch_feeder_hits(
    screen: Screen, run_screen_fn: RunScreenFunction
) -> tuple[ScreenResult | None, str | None]:
    criteria = screen.criteria
    try:
        return run_screen_fn(criteria.filters, criteria.signal, criteria.order), None
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        return None, str(exc)


def run_feeder(
    conn: sqlite3.Connection,
    run_screen_fn: RunScreenFunction,
    now: datetime,
    retention_days: int,
) -> FeederResult:
    feeder_screens = list_feeder_screens(conn)
    tickers_added: list[str] = []
    tickers_updated: list[str] = []
    failed_screens: list[tuple[str, str]] = []

    for screen in feeder_screens:
        result, failure_reason = _fetch_feeder_hits(screen, run_screen_fn)
        if failure_reason is not None:
            failed_screens.append((screen.name, failure_reason))
            continue
        for row in result.rows:
            outcome = record_feeder_hit(conn, row.ticker, row.change_percent, screen.id, now)
            already_counted = row.ticker in tickers_added or row.ticker in tickers_updated
            if not already_counted:
                (tickers_added if outcome == "added" else tickers_updated).append(row.ticker)
        conn.commit()

    return FeederResult(
        screens_run=len(feeder_screens),
        tickers_added=tickers_added,
        tickers_updated=tickers_updated,
        tickers_expired=expire_stale_entries(conn, now, retention_days),
        failed_screens=failed_screens,
    )
