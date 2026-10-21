import asyncio
import logging
from datetime import datetime, timezone

from app.config import Settings
from app.db import connect
from app.finviz_client import run_screen
from app.watchlist.feeder import FeederResult, RunScreenFunction, is_within_feeder_window, run_feeder

logger = logging.getLogger(__name__)

SECONDS_PER_MINUTE = 60


def run_scheduled_feeder_tick(
    db_path: str, now: datetime, retention_days: int, run_screen_fn: RunScreenFunction
) -> FeederResult | None:
    if not is_within_feeder_window(now):
        return None
    try:
        conn = connect(db_path)
        try:
            result = run_feeder(conn, run_screen_fn, now, retention_days)
        finally:
            conn.close()
    except Exception:
        # The loop is the recovery point: an unexpected failure in one tick is
        # logged with its traceback and the next tick tries again, rather than
        # silently killing the background task for the rest of the session.
        logger.exception("feeder tick failed")
        return None

    logger.info(
        "feeder tick: %d screens, %d added, %d updated, %d expired",
        result.screens_run,
        len(result.tickers_added),
        len(result.tickers_updated),
        len(result.tickers_expired),
    )
    if result.failed_screens:
        # WARNING, not INFO: uvicorn configures only its own loggers, so app
        # INFO lines never print. Reasons never contain the auth token.
        logger.warning(
            "feeder screens failed: %s",
            "; ".join(f"{name}: {reason}" for name, reason in result.failed_screens),
        )
    return result


async def feeder_loop(settings: Settings) -> None:
    while True:
        await asyncio.to_thread(
            run_scheduled_feeder_tick,
            settings.db_path,
            datetime.now(timezone.utc),
            settings.watchlist_retention_days,
            run_screen,
        )
        await asyncio.sleep(settings.feeder_interval_minutes * SECONDS_PER_MINUTE)
