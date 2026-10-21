import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import run_screen
from app.routes.dependencies import finviz_error_to_http, get_db_connection
from app.schemas import (
    FormFieldsOut,
    ParseUrlIn,
    ScreenDraft,
    ScreenFormModel,
    ScreenIn,
    ScreenOut,
    ScreenRunOut,
)
from app.screens.filter_form import (
    FORM_OPTIONS,
    SIGNAL_OPTIONS,
    InvalidFormValueError,
    ScreenForm,
    codes_to_form,
    form_to_codes,
)
from app.screens.finviz_url import (
    InvalidScreenerUrlError,
    ScreenCriteria,
    build_finviz_screener_url,
    parse_finviz_screener_url,
)
from app.screens.store import (
    Screen,
    ScreenInput,
    create_screen,
    delete_screen,
    get_screen,
    list_screens,
    update_screen,
)

router = APIRouter(prefix="/api/screens", tags=["screens"])

DbConnection = Annotated[sqlite3.Connection, Depends(get_db_connection)]


def _to_draft(criteria: ScreenCriteria) -> ScreenDraft:
    form, extra_filters = codes_to_form(criteria.filters)
    return ScreenDraft(
        form=ScreenFormModel(**asdict(form)),
        extra_filters=extra_filters,
        signal=criteria.signal,
        order=criteria.order,
    )


def _to_screen_out(screen: Screen) -> ScreenOut:
    return ScreenOut(
        **_to_draft(screen.criteria).model_dump(),
        id=screen.id,
        name=screen.name,
        feeds_watchlist=screen.feeds_watchlist,
        finviz_url=build_finviz_screener_url(screen.criteria),
        created_at=screen.created_at,
        updated_at=screen.updated_at,
    )


def _to_screen_input(body: ScreenIn) -> ScreenInput:
    try:
        form_codes = form_to_codes(ScreenForm(**body.form.model_dump()))
    except InvalidFormValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # A pasted code can duplicate one the form already produces.
    filters = list(dict.fromkeys(form_codes + body.extra_filters))
    return ScreenInput(
        name=body.name,
        criteria=ScreenCriteria(filters, body.signal, body.order),
        feeds_watchlist=body.feeds_watchlist,
    )


def _require_screen(conn: sqlite3.Connection, screen_id: int) -> Screen:
    screen = get_screen(conn, screen_id)
    if screen is None:
        raise HTTPException(status_code=404, detail=f"Screen {screen_id} not found")
    return screen


@router.get("", response_model=list[ScreenOut])
def get_screens(conn: DbConnection) -> list[ScreenOut]:
    return [_to_screen_out(screen) for screen in list_screens(conn)]


@router.post("", response_model=ScreenOut, status_code=201)
def post_screen(body: ScreenIn, conn: DbConnection) -> ScreenOut:
    screen = create_screen(conn, _to_screen_input(body), datetime.now(timezone.utc))
    return _to_screen_out(screen)


@router.get("/form-fields", response_model=FormFieldsOut)
def get_form_fields() -> FormFieldsOut:
    return FormFieldsOut(options=FORM_OPTIONS, signals=SIGNAL_OPTIONS)


@router.post("/parse-url", response_model=ScreenDraft)
def post_parse_url(body: ParseUrlIn) -> ScreenDraft:
    try:
        criteria = parse_finviz_screener_url(body.url)
    except InvalidScreenerUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_draft(criteria)


@router.put("/{screen_id}", response_model=ScreenOut)
def put_screen(screen_id: int, body: ScreenIn, conn: DbConnection) -> ScreenOut:
    screen = update_screen(conn, screen_id, _to_screen_input(body), datetime.now(timezone.utc))
    if screen is None:
        raise HTTPException(status_code=404, detail=f"Screen {screen_id} not found")
    return _to_screen_out(screen)


@router.delete("/{screen_id}", status_code=204)
def remove_screen(screen_id: int, conn: DbConnection) -> Response:
    if not delete_screen(conn, screen_id):
        raise HTTPException(status_code=404, detail=f"Screen {screen_id} not found")
    return Response(status_code=204)


@router.post("/{screen_id}/run", response_model=ScreenRunOut)
def post_run_screen(screen_id: int, conn: DbConnection) -> ScreenRunOut:
    criteria = _require_screen(conn, screen_id).criteria
    try:
        result = run_screen(criteria.filters, criteria.signal, criteria.order)
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        raise finviz_error_to_http(exc) from exc
    return ScreenRunOut(
        rows=[asdict(row) for row in result.rows],
        is_possibly_unfiltered=result.is_possibly_unfiltered,
        fetched_at=datetime.now(timezone.utc),
    )
