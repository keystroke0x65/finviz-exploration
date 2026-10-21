import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.routes.dependencies import get_db_connection
from app.schemas import SettingsIn, SettingsOut
from app.user_settings import get_show_short_setups, set_show_short_setups

router = APIRouter(prefix="/api/settings", tags=["settings"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


@router.get("", response_model=SettingsOut)
def get_settings_route(conn: DbConnection) -> SettingsOut:
    return SettingsOut(show_short_setups=get_show_short_setups(conn))


@router.put("", response_model=SettingsOut)
def put_settings(body: SettingsIn, conn: DbConnection) -> SettingsOut:
    set_show_short_setups(conn, body.show_short_setups)
    return SettingsOut(show_short_setups=get_show_short_setups(conn))
