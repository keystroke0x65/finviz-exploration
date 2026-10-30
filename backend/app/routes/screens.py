import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.errors import FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError
from app.finviz_client import find_unrecognised_codes, run_screen
from app.routes.dependencies import finviz_error_to_http, get_db_connection
from app.routes.setups import to_verdict_out
from app.scanning.verdicts import read_verdicts
from app.schemas import (
    FormFieldsOut,
    ParseUrlIn,
    ParsedScreenDraft,
    ScreenDraft,
    ScreenFormModel,
    ScreenIn,
    ScreenOut,
    ScreenResultRowOut,
    ScreenRunOut,
    ScreenSetupOut,
    SlidingScaleOut,
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
    find_ignored_params,
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
from app.setups.store import SetupRecord, list_current_setups
from app.user_settings import get_show_short_setups

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


def _reject_unrecognised_codes(body: ScreenIn, existing: ScreenCriteria | None = None) -> None:
    # Codes already saved on this screen were checked when they were added, so
    # a rename or feeder toggle costs no Finviz requests.
    known_codes = set(existing.filters) if existing else set()
    new_codes = [code for code in body.extra_filters if code not in known_codes]
    new_signal = body.signal if body.signal and (existing is None or body.signal != existing.signal) else None
    if not new_codes and not new_signal:
        return
    try:
        unrecognised = find_unrecognised_codes(new_codes, new_signal)
    except (FinvizAuthError, FinvizRateLimitError, FinvizUnavailableError) as exc:
        raise finviz_error_to_http(exc) from exc
    if unrecognised:
        raise HTTPException(
            status_code=422,
            detail=f"Finviz doesn't recognise these codes (it would silently ignore them): "
            f"{', '.join(unrecognised)}",
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
    screen_input = _to_screen_input(body)
    _reject_unrecognised_codes(body)
    screen = create_screen(conn, screen_input, datetime.now(timezone.utc))
    return _to_screen_out(screen)


@router.get("/form-fields", response_model=FormFieldsOut)
def get_form_fields() -> FormFieldsOut:
    return FormFieldsOut(options=FORM_OPTIONS, signals=SIGNAL_OPTIONS)


@router.post("/parse-url", response_model=ParsedScreenDraft)
def post_parse_url(body: ParseUrlIn) -> ParsedScreenDraft:
    try:
        criteria = parse_finviz_screener_url(body.url)
    except InvalidScreenerUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParsedScreenDraft(**_to_draft(criteria).model_dump(), ignored_params=find_ignored_params(body.url))


@router.put("/{screen_id}", response_model=ScreenOut)
def put_screen(screen_id: int, body: ScreenIn, conn: DbConnection) -> ScreenOut:
    existing = _require_screen(conn, screen_id)
    screen_input = _to_screen_input(body)
    _reject_unrecognised_codes(body, existing.criteria)
    screen = update_screen(conn, screen_id, screen_input, datetime.now(timezone.utc))
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
    top_setups = _top_setup_by_ticker(conn)
    verdicts = read_verdicts(conn)
    return ScreenRunOut(
        rows=[
            ScreenResultRowOut(
                **asdict(row),
                top_setup=top_setups.get(row.ticker),
                verdict=to_verdict_out(verdicts.get(row.ticker)),
            )
            for row in result.rows
        ],
        fetched_at=datetime.now(timezone.utc),
    )


def _top_setup_by_ticker(conn: sqlite3.Connection) -> dict[str, ScreenSetupOut]:
    """Each stock's highest-scoring setup from the latest scan, as on the Setups tab."""
    show_shorts = get_show_short_setups(conn)
    top_setups: dict[str, ScreenSetupOut] = {}
    # Current setups come best score first, so the first one per ticker wins.
    for record in list_current_setups(conn):
        if record.ticker in top_setups or (record.direction == "short" and not show_shorts):
            continue
        top_setups[record.ticker] = _to_screen_setup_out(record)
    return top_setups


def _to_screen_setup_out(record: SetupRecord) -> ScreenSetupOut:
    scale = record.sliding_scale
    return ScreenSetupOut(
        pattern=record.pattern,
        timeframe=record.timeframe,
        score=record.score,
        sliding_scale=SlidingScaleOut.model_validate(asdict(scale)) if scale else None,
    )
