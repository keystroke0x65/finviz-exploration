"""Request and response models for the journal API.

Inputs forbid unknown fields and carry every limit from the spec, so the rest
of the journal code only ever sees valid drafts.
"""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.journal.positions import MAX_FILLS
from app.journal.reasons import FOLLOWED_PLAN, MISTAKE_KEYS, OTHER_REASON, PASS_REASON_KEYS
from app.schemas import TICKER_BODY_PATTERN, PatternStatsOut, SlidingScaleOut

MAX_PRICE = 100_000
MAX_SHARES = 10_000_000
MAX_FEES = 10_000
MAX_NOTE_LENGTH = 1000
MAX_REASONS = 20
MAX_MISTAKES = 10
MAX_SETTING_DOLLARS = 10_000_000

Ticker = Annotated[str, StringConstraints(pattern=TICKER_BODY_PATTERN, to_upper=True)]
Price = Annotated[float, Field(gt=0, le=MAX_PRICE)]
Note = Annotated[str, StringConstraints(max_length=MAX_NOTE_LENGTH)]


class FillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    side: Literal["buy", "sell"]
    time: AwareDatetime
    price: Price
    shares: Annotated[int, Field(ge=1, le=MAX_SHARES)]


class TradeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["trade"]
    ticker: Ticker
    direction: Literal["long", "short"] = "long"
    setup_record_id: int | None = None
    plan_stop: Price | None = None
    plan_target: Price | None = None
    fees: Annotated[float, Field(ge=0, le=MAX_FEES)] = 0.0
    mistakes: Annotated[list[str], Field(max_length=MAX_MISTAKES)] = []
    note: Note = ""
    fills: Annotated[list[FillIn], Field(min_length=1, max_length=MAX_FILLS)]

    @model_validator(mode="after")
    def check_mistakes(self) -> "TradeIn":
        unknown = [key for key in self.mistakes if key not in MISTAKE_KEYS]
        if unknown:
            raise ValueError(f"Unknown mistake: {', '.join(unknown)}")
        if FOLLOWED_PLAN in self.mistakes and len(set(self.mistakes)) > 1:
            raise ValueError("Followed the plan can't be combined with mistakes.")
        return self


class PassIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["pass"]
    ticker: Ticker
    direction: Literal["long", "short"] = "long"
    setup_record_id: int | None = None
    reasons: Annotated[list[str], Field(min_length=1, max_length=MAX_REASONS)]
    note: Note = ""
    # When the user passed; defaults to now.
    decided_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def check_reasons(self) -> "PassIn":
        unknown = [key for key in self.reasons if key not in PASS_REASON_KEYS]
        if unknown:
            raise ValueError(f"Unknown reason: {', '.join(unknown)}")
        if OTHER_REASON in self.reasons and not self.note.strip():
            raise ValueError("Add a note to explain the Other reason.")
        return self


EntryIn = Annotated[TradeIn | PassIn, Field(discriminator="kind")]


class FillOut(BaseModel):
    side: Literal["buy", "sell"]
    time: datetime
    price: float
    shares: int


class ClosedPnlOut(BaseModel):
    time: datetime
    pnl: float


class TradeFiguresOut(BaseModel):
    status: Literal["open", "closed"]
    first_price: float
    average_entry: float
    average_exit: float | None
    shares_held: int
    max_shares: int
    money_in: float
    total_bought: float
    realised_pnl: float
    closed_pnl: list[ClosedPnlOut]
    fees: float
    net_pnl: float
    r_multiple: float | None
    planned_reward_risk: float | None
    opened_at: datetime
    last_fill_at: datetime
    duration_seconds: float


class SetupSnapshotOut(BaseModel):
    setup_record_id: int | None
    pattern: str
    timeframe: str
    direction: str
    entry: float
    stop: float
    target: float
    reward_risk: float
    score: float
    state: str
    verdict: str | None
    sliding_scale: SlidingScaleOut | None


class StockFactsOut(BaseModel):
    company: str | None
    country: str | None
    sector: str | None
    industry: str | None
    market_cap_millions: float | None
    float_millions: float | None
    price: float | None
    change_percent: float | None
    volume_so_far: int | None
    volume_vs_average: float | None


class AfterExitOut(BaseModel):
    best_r: float | None
    worst_r: float | None
    best_price: float | None
    worst_price: float | None


class PassScoreOut(BaseModel):
    outcome: Literal["target", "stop", "never_filled", "undecided", "not_scored"]
    r: float | None


class JournalEntryOut(BaseModel):
    id: int
    kind: Literal["trade", "pass"]
    ticker: str
    direction: Literal["long", "short"]
    created_at: datetime
    updated_at: datetime
    decided_at: datetime
    setup: SetupSnapshotOut | None
    stock: StockFactsOut
    plan_stop: float | None
    plan_target: float | None
    fees: float
    reasons: list[str]
    mistakes: list[str]
    note: str
    pass_price: float | None
    fills: list[FillOut]
    figures: TradeFiguresOut | None
    after_exit: AfterExitOut | None
    plan_flags: list[Literal["exited_before_target", "held_past_stop", "followed_plan"]]
    pass_score: PassScoreOut | None
    # Set only on the response to a save whose chart bars couldn't be fetched.
    bar_warning: str | None = None


class PreviewOut(BaseModel):
    figures: TradeFiguresOut | None
    error: str | None


class ReasonItemOut(BaseModel):
    key: str
    label: str


class ReasonGroupOut(BaseModel):
    group: str
    items: list[ReasonItemOut]


class ReasonCatalogOut(BaseModel):
    pass_reasons: list[ReasonGroupOut]
    mistakes: list[ReasonItemOut]


class JournalBarOut(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class BarDayOut(BaseModel):
    day: date
    status: Literal["partial", "complete", "missing", "incomplete"] | None


class EntryBarsOut(BaseModel):
    bars: list[JournalBarOut]
    days: list[BarDayOut]


class DaySetupOut(BaseModel):
    setup_record_id: int
    pattern: str
    timeframe: str
    direction: str
    entry: float
    stop: float
    target: float
    reward_risk: float
    score: float
    state: str
    verdict: str | None
    sliding_scale: SlidingScaleOut | None
    outcome: str


class BucketOut(BaseModel):
    label: str
    count: int
    pnl: float


class PnlPointOut(BaseModel):
    time: datetime
    pnl: float
    cumulative: float


class PassReasonRowOut(BaseModel):
    reason: str
    count: int
    target: int
    stop: int
    never_filled: int
    undecided: int
    average_r: float | None


class VersusRowOut(BaseModel):
    pattern: str
    timeframe: str
    trades: int
    win_rate: float | None
    average_r: float | None
    system: PatternStatsOut | None
    system_has_enough_history: bool


class JournalSummaryOut(BaseModel):
    net_pnl: float
    trades: int
    wins: int
    losses: int
    win_rate: float | None
    average_gain: float | None
    average_loss: float | None
    largest_win: float | None
    largest_loss: float | None
    average_planned_reward_risk: float | None
    average_r: float | None
    average_duration_seconds: float | None
    average_sykes_points: float | None
    average_sykes_letter: str | None
    average_score: float | None
    average_left_on_table_r: float | None
    passes: int
    open_trades: int
    pnl_points: list[PnlPointOut]
    by_country: list[BucketOut]
    by_industry: list[BucketOut]
    by_pattern: list[BucketOut]
    by_mistake: list[BucketOut]
    by_time_of_day: list[BucketOut]
    by_duration: list[BucketOut]
    pass_reasons: list[PassReasonRowOut]
    versus_system: list[VersusRowOut]


class DailyLossOut(BaseModel):
    realised_pnl_today: float
    max_daily_loss: float | None
    level: Literal["ok", "warning", "reached"]


SettingDollars = Annotated[float, Field(gt=0, le=MAX_SETTING_DOLLARS)]


class JournalSettingsIO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_per_trade: SettingDollars | None
    max_position: SettingDollars | None
    max_daily_loss: SettingDollars | None
