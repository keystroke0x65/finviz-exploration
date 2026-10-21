import sqlite3
from collections.abc import Iterator

from fastapi import HTTPException

from app.config import get_settings
from app.db import connect
from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError


def get_db_connection() -> Iterator[sqlite3.Connection]:
    conn = connect(get_settings().db_path)
    try:
        yield conn
    finally:
        conn.close()


def finviz_error_to_http(
    exc: FinvizAuthError | FinvizRateLimitError | FinvizUnavailableError,
) -> HTTPException:
    if isinstance(exc, FinvizAuthError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, FinvizRateLimitError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=504, detail=str(exc))
