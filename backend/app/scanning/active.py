"""Chooses which watchlist tickers get a full bar scan.

The watchlist can hold hundreds of names and each scan costs three bar requests
per ticker, so only names that are moving now are scanned.
"""

from app.finviz_client import ScreenRow

MAX_ACTIVE_TICKERS = 40
MIN_RELATIVE_VOLUME = 1.5
MIN_ABS_CHANGE_PERCENT = 5.0


def _largest_move(row: ScreenRow) -> float:
    return max(abs(row.change_percent or 0), abs(row.after_hours_change_percent or 0))


def _is_active(row: ScreenRow, screen_hits: set[str]) -> bool:
    return (
        row.ticker in screen_hits
        or (row.relative_volume or 0) >= MIN_RELATIVE_VOLUME
        or _largest_move(row) >= MIN_ABS_CHANGE_PERCENT
    )


def select_active_tickers(snapshots: list[ScreenRow], screen_hits: set[str]) -> list[str]:
    active = [row for row in snapshots if _is_active(row, screen_hits)]
    active.sort(key=lambda row: (row.ticker not in screen_hits, -(row.relative_volume or 0), -_largest_move(row)))
    return [row.ticker for row in active[:MAX_ACTIVE_TICKERS]]
