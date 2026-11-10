import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from app.routes.dependencies import get_db_connection
from app.journal.schemas import JournalSettingsIO
from app.schemas import ColumnWidths, SettingsIn, SettingsOut
from app.user_settings import (
    get_journal_settings,
    get_screen_column_widths,
    get_show_short_setups,
    set_journal_settings,
    set_screen_column_widths,
    set_show_short_setups,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


@router.get("", response_model=SettingsOut)
def get_settings_route(conn: DbConnection) -> SettingsOut:
    return SettingsOut(show_short_setups=get_show_short_setups(conn))


@router.put("", response_model=SettingsOut)
def put_settings(body: SettingsIn, conn: DbConnection) -> SettingsOut:
    set_show_short_setups(conn, body.show_short_setups)
    return SettingsOut(show_short_setups=get_show_short_setups(conn))


@router.get("/screen-column-widths", response_model=ColumnWidths)
def get_screen_column_widths_route(conn: DbConnection) -> ColumnWidths:
    return ColumnWidths(widths=get_screen_column_widths(conn))


@router.put("/screen-column-widths", response_model=ColumnWidths)
def put_screen_column_widths(body: ColumnWidths, conn: DbConnection) -> ColumnWidths:
    set_screen_column_widths(conn, body.widths)
    return ColumnWidths(widths=get_screen_column_widths(conn))


@router.get("/journal", response_model=JournalSettingsIO)
def get_journal_settings_route(conn: DbConnection) -> JournalSettingsIO:
    return JournalSettingsIO(**get_journal_settings(conn))


@router.put("/journal", response_model=JournalSettingsIO)
def put_journal_settings(body: JournalSettingsIO, conn: DbConnection) -> JournalSettingsIO:
    set_journal_settings(conn, body.model_dump())
    return JournalSettingsIO(**get_journal_settings(conn))
