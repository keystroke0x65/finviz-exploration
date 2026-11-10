"""Journal totals and breakdowns for a period.

Two clocks, so every total agrees with the P&L chart and the daily loss warning:
- Money: realised P&L is booked at each closing fill; fees with a trade's last fill.
- Trade statistics (counts, win rate, averages, breakdowns): a trade belongs to
  the period of its last fill, and only closed trades count.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from statistics import mean
from typing import Callable, Literal

from app.journal.pass_scoring import AfterPass, PassScore
from app.journal.positions import TradeFigures
from app.journal.review import AfterExit, PlanFlag
from app.journal.store import JournalEntry
from app.market_time import EASTERN
from app.patterns.sliding_scale import FAILING_LETTER, LETTER_FLOORS
from app.setups.track_record import PatternStats, has_enough_history

Period = Literal["today", "week", "month", "all"]
SystemStats = Callable[[str, str], PatternStats | None]

NO_SETUP = "no_setup"
UNKNOWN = "Unknown"
TIME_OF_DAY_BUCKETS: list[tuple[time, str]] = [
    (time(9, 30), "4:00–9:30"),
    (time(10, 0), "9:30–10"),
    (time(11, 0), "10–11"),
    (time(12, 0), "11–12"),
    (time(14, 0), "12–2"),
    (time(16, 0), "2–4"),
    (time(23, 59, 59), "4–8 PM"),
]
FIVE_MINUTES = 5 * 60
THIRTY_MINUTES = 30 * 60
DURATION_LABELS = ["Under 5 min", "5–30 min", "30 min to close", "Multi-day"]


@dataclass(frozen=True)
class ReviewedTrade:
    entry: JournalEntry
    figures: TradeFigures
    after: AfterExit | None
    flags: list[PlanFlag]


@dataclass(frozen=True)
class ScoredPass:
    entry: JournalEntry
    score: PassScore
    after: AfterPass | None = None


@dataclass(frozen=True)
class Bucket:
    label: str
    count: int
    pnl: float


@dataclass(frozen=True)
class PnlPoint:
    time: datetime
    pnl: float
    cumulative: float


@dataclass(frozen=True)
class PassReasonRow:
    reason: str
    count: int
    target: int
    stop: int
    never_filled: int
    undecided: int
    # Price was already past the target or behind the stop when the user passed.
    already_past: int
    # Over passes that would have hit their target or stop.
    average_r: float | None
    # Best and worst move after passing, from the pass price, over passes with bars.
    average_best_percent: float | None
    average_worst_percent: float | None


@dataclass(frozen=True)
class VersusRow:
    pattern: str
    timeframe: str
    trades: int
    win_rate: float | None
    average_r: float | None
    system: PatternStats | None
    system_has_enough_history: bool


@dataclass(frozen=True)
class JournalSummary:
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
    pnl_points: list[PnlPoint]
    by_country: list[Bucket]
    by_industry: list[Bucket]
    by_pattern: list[Bucket]
    by_mistake: list[Bucket]
    by_time_of_day: list[Bucket]
    by_duration: list[Bucket]
    pass_reasons: list[PassReasonRow]
    versus_system: list[VersusRow]


def period_start(period: Period, now: datetime) -> datetime | None:
    today = now.astimezone(EASTERN).date()
    if period == "all":
        return None
    if period == "week":
        today -= timedelta(days=today.weekday())
    elif period == "month":
        today = today.replace(day=1)
    return datetime.combine(today, time(0), tzinfo=EASTERN)


def _is_in_period(moment: datetime, start: datetime | None) -> bool:
    return start is None or moment >= start


def _average(values: list[float]) -> float | None:
    return mean(values) if values else None


def _pnl_points(trades: list[ReviewedTrade], start: datetime | None) -> list[PnlPoint]:
    booked: list[tuple[datetime, float]] = []
    for trade in trades:
        figures = trade.figures
        for index, closed in enumerate(figures.closed_pnl):
            is_final = figures.status == "closed" and index == len(figures.closed_pnl) - 1
            booked.append((closed.time, closed.pnl - (figures.fees if is_final else 0.0)))
    points: list[PnlPoint] = []
    cumulative = 0.0
    for moment, pnl in sorted(booked, key=lambda item: item[0]):
        if not _is_in_period(moment, start):
            continue
        cumulative += pnl
        points.append(PnlPoint(moment, pnl, cumulative))
    return points


def _grouped(trades: list[ReviewedTrade], labels_of: Callable[[ReviewedTrade], list[str]]) -> list[Bucket]:
    groups: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        for label in labels_of(trade):
            groups[label].append(trade.figures.net_pnl)
    buckets = [Bucket(label, len(pnls), sum(pnls)) for label, pnls in groups.items()]
    return sorted(buckets, key=lambda bucket: (-bucket.count, bucket.label))


def _in_fixed_order(trades: list[ReviewedTrade], labels: list[str], label_of: Callable[[ReviewedTrade], str]) -> list[Bucket]:
    found = {bucket.label: bucket for bucket in _grouped(trades, lambda trade: [label_of(trade)])}
    return [found.get(label, Bucket(label, 0, 0.0)) for label in labels]


def _time_of_day_label(trade: ReviewedTrade) -> str:
    opened = trade.figures.opened_at.astimezone(EASTERN).time()
    return next(label for end, label in TIME_OF_DAY_BUCKETS if opened < end)


def _duration_label(trade: ReviewedTrade) -> str:
    figures = trade.figures
    if figures.duration_seconds < FIVE_MINUTES:
        return DURATION_LABELS[0]
    if figures.duration_seconds < THIRTY_MINUTES:
        return DURATION_LABELS[1]
    is_same_day = figures.opened_at.astimezone(EASTERN).date() == figures.last_fill_at.astimezone(EASTERN).date()
    return DURATION_LABELS[2] if is_same_day else DURATION_LABELS[3]


def _letter_for(points: float | None) -> str | None:
    if points is None:
        return None
    return next((letter for floor, letter in LETTER_FLOORS if points >= floor), FAILING_LETTER)


def _pass_reason_rows(passes: list[ScoredPass]) -> list[PassReasonRow]:
    by_reason: dict[str, list[ScoredPass]] = defaultdict(list)
    for scored in passes:
        for reason in scored.entry.reasons:
            by_reason[reason].append(scored)
    rows = []
    for reason, group in by_reason.items():
        scores = [scored.score for scored in group]
        afters = [scored.after for scored in group if scored.after is not None]
        outcomes = [score.outcome for score in scores]
        rows.append(PassReasonRow(
            reason=reason,
            count=len(scores),
            target=outcomes.count("target"),
            stop=outcomes.count("stop"),
            never_filled=outcomes.count("never_filled"),
            undecided=outcomes.count("undecided"),
            already_past=outcomes.count("past_target") + outcomes.count("behind_stop"),
            average_r=_average([score.r for score in scores if score.r is not None]),
            average_best_percent=_average([after.best_percent for after in afters]),
            average_worst_percent=_average([after.worst_percent for after in afters]),
        ))
    return sorted(rows, key=lambda row: (-row.count, row.reason))


def _versus_rows(trades: list[ReviewedTrade], system_stats: SystemStats) -> list[VersusRow]:
    groups: dict[tuple[str, str], list[ReviewedTrade]] = defaultdict(list)
    for trade in trades:
        if trade.entry.setup is not None:
            groups[(trade.entry.setup.pattern, trade.entry.setup.timeframe)].append(trade)
    rows = []
    for (pattern, timeframe), group in groups.items():
        wins = sum(1 for trade in group if trade.figures.net_pnl > 0)
        decided = sum(1 for trade in group if trade.figures.net_pnl != 0)
        system = system_stats(pattern, timeframe)
        rows.append(VersusRow(
            pattern=pattern,
            timeframe=timeframe,
            trades=len(group),
            win_rate=wins / decided if decided else None,
            average_r=_average([trade.figures.r_multiple for trade in group if trade.figures.r_multiple is not None]),
            system=system,
            system_has_enough_history=has_enough_history(system),
        ))
    return sorted(rows, key=lambda row: (-row.trades, row.pattern, row.timeframe))


def summarise(
    trades: list[ReviewedTrade],
    passes: list[ScoredPass],
    start: datetime | None,
    system_stats: SystemStats,
) -> JournalSummary:
    closed = [
        trade for trade in trades
        if trade.figures.status == "closed" and _is_in_period(trade.figures.last_fill_at, start)
    ]
    period_passes = [scored for scored in passes if _is_in_period(scored.entry.decided_at, start)]
    pnls = [trade.figures.net_pnl for trade in closed]
    gains = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    setups = [trade.entry.setup for trade in closed if trade.entry.setup is not None]
    sykes_points = _average([setup.sliding_scale.points for setup in setups if setup.sliding_scale is not None])
    points = _pnl_points(trades, start)
    return JournalSummary(
        net_pnl=points[-1].cumulative if points else 0.0,
        trades=len(closed),
        wins=len(gains),
        losses=len(losses),
        win_rate=len(gains) / (len(gains) + len(losses)) if gains or losses else None,
        average_gain=_average(gains),
        average_loss=_average(losses),
        largest_win=max(gains) if gains else None,
        largest_loss=min(losses) if losses else None,
        average_planned_reward_risk=_average(
            [trade.figures.planned_reward_risk for trade in closed if trade.figures.planned_reward_risk is not None]),
        average_r=_average([trade.figures.r_multiple for trade in closed if trade.figures.r_multiple is not None]),
        average_duration_seconds=_average([trade.figures.duration_seconds for trade in closed]),
        average_sykes_points=sykes_points,
        average_sykes_letter=_letter_for(sykes_points),
        average_score=_average([setup.score for setup in setups]),
        average_left_on_table_r=_average(
            [trade.after.best_r for trade in closed if trade.after is not None and trade.after.best_r is not None]),
        passes=len(period_passes),
        open_trades=sum(1 for trade in trades if trade.figures.status == "open"),
        pnl_points=points,
        by_country=_grouped(closed, lambda trade: [trade.entry.stock.country or UNKNOWN]),
        by_industry=_grouped(closed, lambda trade: [trade.entry.stock.industry or UNKNOWN]),
        by_pattern=_grouped(closed, lambda trade: [trade.entry.setup.pattern if trade.entry.setup else NO_SETUP]),
        by_mistake=_grouped(closed, lambda trade: trade.entry.mistakes),
        by_time_of_day=_in_fixed_order(closed, [label for _, label in TIME_OF_DAY_BUCKETS], _time_of_day_label),
        by_duration=_in_fixed_order(closed, DURATION_LABELS, _duration_label),
        pass_reasons=_pass_reason_rows(period_passes),
        versus_system=_versus_rows(closed, system_stats),
    )


def daily_realised_pnl(trades: list[ReviewedTrade], now: datetime) -> float:
    """Today's realised P&L after fees, for the max daily loss warning."""
    today = period_start("today", now)
    return sum(point.pnl for point in _pnl_points(trades, today))
