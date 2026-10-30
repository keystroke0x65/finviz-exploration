from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.screens.filter_form import MarketCapOption
from app.screens.finviz_url import CODE_PATTERN, MAX_FILTER_CODES, MAX_URL_LENGTH


class QuoteResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    Ticker: str
    Company: str | None = None
    Price: str | None = None


MAX_SCREEN_NAME_LENGTH = 80
# Same shape as Phase 1's ticker path parameter (letters plus '.'/'-').
TICKER_BODY_PATTERN = r"^[A-Za-z.\-]{1,10}$"

FinvizCode = Annotated[str, StringConstraints(pattern=CODE_PATTERN)]


class ScreenFormModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: Literal["usa"] | None = None
    price_under: float | None = None
    float_under_millions: float | None = None
    market_cap: MarketCapOption | None = None
    volume_over_thousands: int | None = None
    relative_volume_over: float | None = None


class ScreenIn(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_SCREEN_NAME_LENGTH),
    ]
    form: ScreenFormModel = ScreenFormModel()
    extra_filters: Annotated[list[FinvizCode], Field(max_length=MAX_FILTER_CODES)] = []
    signal: FinvizCode | None = None
    order: FinvizCode | None = None
    feeds_watchlist: bool = False


class ScreenDraft(BaseModel):
    form: ScreenFormModel
    extra_filters: list[str]
    signal: str | None
    order: str | None


class ParsedScreenDraft(ScreenDraft):
    # URL parameters the saved screen won't keep, shown so the user knows.
    ignored_params: list[str]


class ScreenOut(ScreenDraft):
    id: int
    name: str
    feeds_watchlist: bool
    finviz_url: str
    created_at: datetime
    updated_at: datetime


class ParseUrlIn(BaseModel):
    url: Annotated[str, StringConstraints(max_length=MAX_URL_LENGTH)]


class ScreenRowOut(BaseModel):
    ticker: str
    company: str | None
    country: str | None
    market_cap_millions: float | None
    float_millions: float | None
    average_volume_thousands: float | None
    relative_volume: float | None
    price: float | None
    change_percent: float | None
    volume: int | None
    after_hours_close: float | None
    after_hours_change_percent: float | None
    news_time: datetime | None
    news_url: str | None
    news_title: str | None


class FormFieldsOut(BaseModel):
    options: dict[str, list]
    signals: dict[str, str]


class AppearanceOut(BaseModel):
    seen_on: date
    change_percent: float | None
    screen_id: int
    screen_name: str | None = None


class VerdictOut(BaseModel):
    call: Literal["leans_long", "leans_short", "no_clear_edge"]
    score: float
    parts: dict[str, float]
    reasons: list[str]
    computed_at: datetime


class SnapshotOut(BaseModel):
    price: float | None
    change_percent: float | None
    after_hours_change_percent: float | None
    relative_volume: float | None
    fetched_at: datetime


class WatchlistEntryOut(BaseModel):
    ticker: str
    source: Literal["auto", "manual"]
    added_at: datetime
    last_seen_in_feeder_at: datetime | None
    is_pinned: bool
    expires_at: datetime | None
    appearances: list[AppearanceOut]
    snapshot: SnapshotOut | None = None
    verdict: VerdictOut | None = None


class AddTickerIn(BaseModel):
    ticker: Annotated[str, StringConstraints(strip_whitespace=True, pattern=TICKER_BODY_PATTERN)]


class PinIn(BaseModel):
    is_pinned: bool


class FailedScreenOut(BaseModel):
    screen: str
    reason: str


class FeederResultOut(BaseModel):
    screens_run: int
    tickers_added: list[str]
    tickers_updated: list[str]
    tickers_expired: list[str]
    failed_screens: list[FailedScreenOut]


class FeederStatusOut(FeederResultOut):
    finished_at: datetime


# --- Bars, scans, setups, settings (phase 2, milestone 2a) ---


class BarOut(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceLevelOut(BaseModel):
    price: float
    touches: int


class SessionLevelsOut(BaseModel):
    premarket_high: float | None
    premarket_low: float | None
    day_high: float | None
    day_low: float | None
    opening_range_high: float | None
    opening_range_low: float | None
    previous_close: float | None


class BarsOut(BaseModel):
    bars: list[BarOut]
    fetched_at: datetime
    daily_levels: list[PriceLevelOut]
    session: SessionLevelsOut | None
    vwap: list[float | None] | None


class ScanIn(BaseModel):
    ticker: Annotated[str, StringConstraints(strip_whitespace=True, pattern=TICKER_BODY_PATTERN)] | None = None


class FailedTickerOut(BaseModel):
    ticker: str
    reason: str


class ScanOut(BaseModel):
    scanned: list[str]
    failed: list[FailedTickerOut]
    setups_found: int
    scanned_at: datetime


class CompletedScanOut(BaseModel):
    status: Literal["completed"] = "completed"
    finished_at: datetime
    scanned: int
    failed: list[FailedTickerOut]


class CrashedScanOut(BaseModel):
    status: Literal["crashed"] = "crashed"
    finished_at: datetime
    error_type: str


class ScanStatusOut(BaseModel):
    """The latest full scan (scheduled or from the page) and whether scans have stalled."""

    latest: Annotated[CompletedScanOut | CrashedScanOut, Field(discriminator="status")] | None
    last_completed_at: datetime | None
    is_overdue: bool


class SlidingScaleFactorOut(BaseModel):
    name: str
    grade: Literal["good", "ok", "poor", "no_data"]
    detail: str


class SlidingScaleOut(BaseModel):
    """Our grading of Tim Sykes's sliding scale: seven factors, 2/1/0 points each."""

    letter: Literal["A", "B", "C", "D", "F"]
    points: int
    factors: list[SlidingScaleFactorOut]


class ScreenSetupOut(BaseModel):
    """A stock's best current setup, as shown beside a screen result."""

    pattern: str
    timeframe: Literal["1m", "5m", "daily"]
    score: float
    sliding_scale: SlidingScaleOut | None


class ScreenResultRowOut(ScreenRowOut):
    # None when the stock has no setup in the latest scan (or was never scanned).
    top_setup: ScreenSetupOut | None = None
    verdict: VerdictOut | None = None


class ScreenRunOut(BaseModel):
    rows: list[ScreenResultRowOut]
    fetched_at: datetime


class SetupOut(BaseModel):
    id: int
    ticker: str
    pattern: str
    direction: Literal["long", "short"]
    timeframe: Literal["1m", "5m", "daily"]
    entry: float
    stop: float
    capped_target: float
    target_3r: float
    available_reward_risk: float
    risk_percent: float
    blocking_level: float | None
    partial_1r: float
    partial_2r: float
    trailing_stop: float | None
    quality: float
    score: float
    score_parts: dict[str, float]
    key_points: list[tuple[datetime, float]]
    state: Literal["forming", "triggered", "extended", "invalidated"]
    triggered_at: datetime | None  # when price last reached the entry (None while forming)
    session: str
    detected_at: datetime
    last_seen_at: datetime
    has_conflict: bool
    verdict: VerdictOut | None = None
    track_record: "TrackRecordSummaryOut | None" = None
    sliding_scale: SlidingScaleOut | None = None


class WarningOut(BaseModel):
    """A bearish pattern shown while short setups are off: what and where, never a
    short trade plan (no stop, targets or reward:risk)."""

    id: int
    ticker: str
    pattern: str
    direction: Literal["long", "short"]
    timeframe: Literal["1m", "5m", "daily"]
    entry: float  # the breakdown level
    state: Literal["forming", "triggered", "extended", "invalidated"]
    triggered_at: datetime | None
    key_points: list[tuple[datetime, float]]
    detected_at: datetime
    last_seen_at: datetime
    verdict: VerdictOut | None = None


class TrackRecordSummaryOut(BaseModel):
    trades: int
    win_rate: float | None
    average_r: float | None
    average_win_r: float | None
    tickers: int
    trading_days: int
    has_enough_history: bool  # whether this history is moving the setup's score


SetupOut.model_rebuild()


class SetupsOut(BaseModel):
    setups: list[SetupOut]
    warnings: list[WarningOut]
    show_short_setups: bool


class SettingsOut(BaseModel):
    show_short_setups: bool


class SettingsIn(BaseModel):
    show_short_setups: Annotated[bool, Field(strict=True)]


# --- Track record (phase 2, milestone 3) ---


class PatternStatsOut(BaseModel):
    pattern: str
    timeframe: str
    trades: int
    wins: int
    losses: int
    expired_after_fill: int
    win_rate: float | None
    average_r: float | None
    average_win_r: float | None
    average_max_favorable_r: float | None
    not_trades: int
    still_open: int
    tickers: int
    trading_days: int
    first_day: str | None
    last_day: str | None
    has_enough_history: bool


class TrackRecordOut(BaseModel):
    rows: list[PatternStatsOut]
    min_trades: int
    min_trading_days: int
