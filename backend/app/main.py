import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone

from fastapi import FastAPI

from app.config import get_settings
from app.db import connect
from app.routes.bars import router as bars_router
from app.routes.screens import router as screens_router
from app.routes.settings import router as settings_router
from app.routes.setups import router as setups_router
from app.routes.stocks import router as stocks_router
from app.routes.track_record import router as track_record_router
from app.routes.watchlist import router as watchlist_router
from app.screens.store import seed_default_screens
from app.watchlist.scheduler import feeder_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    conn = connect(settings.db_path)
    try:
        seed_default_screens(conn, datetime.now(timezone.utc))
    finally:
        conn.close()

    feeder_task = asyncio.create_task(feeder_loop(settings)) if settings.is_feeder_enabled else None
    yield
    if feeder_task is not None:
        feeder_task.cancel()
        with suppress(asyncio.CancelledError):
            await feeder_task


app = FastAPI(title="Finviz Dashboard API", lifespan=lifespan)
app.include_router(stocks_router)
app.include_router(screens_router)
app.include_router(watchlist_router)
app.include_router(bars_router)
app.include_router(setups_router)
app.include_router(settings_router)
app.include_router(track_record_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
