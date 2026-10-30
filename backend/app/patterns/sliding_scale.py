"""Our grading of Tim Sykes's sliding scale (P.R.E.P.A.R.E.) for a setup.

Sykes publishes the seven factors but not a scoring formula, so the thresholds
here come from what he and reporters have published where possible, and are our
call otherwise. docs/superpowers/specs/2026-10-28-sykes-sliding-scale-design.md
lists each threshold with its source.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.finviz_client import Bar, ScreenRow
from app.market_time import EASTERN
from app.patterns.types import SetupState

FactorGrade = Literal["good", "ok", "poor", "no_data"]

GRADE_POINTS: dict[FactorGrade, int] = {"good": 2, "ok": 1, "poor": 0, "no_data": 1}
# Lowest total for each letter, best first; anything lower is an F.
LETTER_FLOORS = [(12, "A"), (10, "B"), (8, "C"), (6, "D")]
FAILING_LETTER = "F"

# Pattern quality from the detectors runs 0-1.
CLEAN_PATTERN_QUALITY = 0.7
# Sykes: 1:2 is "not enough"; he looks for 1:3 or 1:4.
WANTED_REWARD_RISK = 3.0
NOT_ENOUGH_REWARD_RISK = 2.0
# He trades stocks averaging 1-5M shares a day.
LIQUID_SHARES = 1_000_000
TRADEABLE_SHARES = 500_000
# A spike day: high at least 30% over the previous close (his 30%+ gainers watchlist).
SPIKE_RATIO = 1.30
SPIKE_LOOKBACK = timedelta(days=365)
FREQUENT_SPIKE_DAYS = 3
FRESH_NEWS = timedelta(hours=24)
RECENT_NEWS = timedelta(days=3)
# A "hot" day has enough 30%+ gainers to fill his 10-15 stock watchlist.
HOT_MARKET_GAINERS = 10
ACTIVE_MARKET_GAINERS = 5

REGULAR_OPEN = time(9, 30)
MORNING_POWER_HOUR_END = time(10, 30)
CLOSING_POWER_HOUR_START = time(15, 0)
REGULAR_CLOSE = time(16, 0)


@dataclass(frozen=True)
class Factor:
    name: str
    grade: FactorGrade
    detail: str


@dataclass(frozen=True)
class SlidingScale:
    letter: str
    points: int
    factors: list[Factor]


@dataclass(frozen=True)
class MarketGainers:
    count: int
    # Before the open, Finviz's change is still the previous session's.
    is_previous_session: bool


@dataclass(frozen=True)
class SlidingScaleInputs:
    quality: float
    state: SetupState
    reward_risk: float
    snapshot: ScreenRow | None
    spike_days: int | None
    # When the setup triggered, or the scan time while it's still forming.
    setup_time: datetime
    market_gainers: MarketGainers | None
    now: datetime


def count_spike_days(daily_bars: list[Bar], today: date) -> int:
    """Days in the past year, before today, whose high was 30%+ over the previous close."""
    earliest = today - SPIKE_LOOKBACK
    return sum(
        1
        for previous, bar in zip(daily_bars, daily_bars[1:])
        if earliest < bar.time.astimezone(EASTERN).date() < today and bar.high >= previous.close * SPIKE_RATIO
    )


def _format_shares(shares: float) -> str:
    if shares >= 1_000_000:
        return f"{shares / 1_000_000:.1f}M"
    if shares >= 1_000:
        return f"{shares / 1_000:.0f}K"
    return f"{shares:.0f}"


def _format_clock(moment: datetime) -> str:
    return moment.astimezone(EASTERN).strftime("%-I:%M %p")


def _grade_pattern_and_price(quality: float, state: SetupState) -> Factor:
    is_clean = quality >= CLEAN_PATTERN_QUALITY
    is_extended = state == "extended"
    passed = int(is_clean) + int(not is_extended)
    grade: FactorGrade = ("poor", "ok", "good")[passed]
    position = "extended past entry" if is_extended else "not extended"
    return Factor("Pattern & price", grade, f"Quality {quality:.2f}, {position}")


def _grade_reward_risk(reward_risk: float) -> Factor:
    if reward_risk >= WANTED_REWARD_RISK:
        grade: FactorGrade = "good"
    elif reward_risk > NOT_ENOUGH_REWARD_RISK:
        grade = "ok"
    else:
        grade = "poor"
    return Factor("Risk/reward", grade, f"{reward_risk:.1f}R (wants 3R+)")


def _grade_entry_exit_ease(snapshot: ScreenRow | None) -> Factor:
    name = "Entry/exit ease"
    if snapshot is None or (snapshot.volume is None and snapshot.average_volume_thousands is None):
        return Factor(name, "no_data", "No volume data")
    today = snapshot.volume or 0
    average = (snapshot.average_volume_thousands or 0) * 1_000
    shares = max(today, average)
    if shares >= LIQUID_SHARES:
        grade: FactorGrade = "good"
    elif shares >= TRADEABLE_SHARES:
        grade = "ok"
    else:
        grade = "poor"
    return Factor(name, grade, f"{_format_shares(today)} shares today, {_format_shares(average)} average")


def _grade_past_spikes(spike_days: int | None) -> Factor:
    name = "Past spikes"
    if spike_days is None:
        return Factor(name, "no_data", "No daily history")
    if spike_days >= FREQUENT_SPIKE_DAYS:
        grade: FactorGrade = "good"
    elif spike_days > 0:
        grade = "ok"
    else:
        grade = "poor"
    return Factor(name, grade, f"{spike_days} days up 30%+ in the past year")


def _grade_time(setup_time: datetime) -> Factor:
    clock = setup_time.astimezone(EASTERN).time()
    if clock < REGULAR_OPEN:
        grade, label = "poor", "Pre-market"
    elif clock < MORNING_POWER_HOUR_END:
        grade, label = "good", "Power hour"
    elif clock < CLOSING_POWER_HOUR_START:
        grade, label = "ok", "Midday"
    elif clock < REGULAR_CLOSE:
        grade, label = "good", "Power hour"
    else:
        grade, label = "poor", "After-hours"
    return Factor("Time", grade, f"{label} ({_format_clock(setup_time)})")


def _grade_catalyst(snapshot: ScreenRow | None, now: datetime) -> Factor:
    name = "Catalyst"
    if snapshot is None:
        return Factor(name, "no_data", "No news data")
    news_time = snapshot.news_time
    if news_time is None or now - news_time > RECENT_NEWS:
        return Factor(name, "poor", "No news in the last 3 days")
    stamp = f"News {news_time.astimezone(EASTERN).strftime('%b %-d')}, {_format_clock(news_time)}"
    if now - news_time <= FRESH_NEWS:
        return Factor(name, "good", stamp)
    return Factor(name, "ok", f"{stamp} (over 24 hours ago)")


def _grade_market(market_gainers: MarketGainers | None) -> Factor:
    name = "Market"
    if market_gainers is None:
        return Factor(name, "no_data", "No market data")
    count = market_gainers.count
    if count >= HOT_MARKET_GAINERS:
        grade: FactorGrade = "good"
    elif count >= ACTIVE_MARKET_GAINERS:
        grade = "ok"
    else:
        grade = "poor"
    when = "in the previous session" if market_gainers.is_previous_session else "today"
    return Factor(name, grade, f"{count} US stocks up 30%+ {when}")


def _letter_for(points: int) -> str:
    return next((letter for floor, letter in LETTER_FLOORS if points >= floor), FAILING_LETTER)


def grade_sliding_scale(inputs: SlidingScaleInputs) -> SlidingScale:
    factors = [
        _grade_pattern_and_price(inputs.quality, inputs.state),
        _grade_reward_risk(inputs.reward_risk),
        _grade_entry_exit_ease(inputs.snapshot),
        _grade_past_spikes(inputs.spike_days),
        _grade_time(inputs.setup_time),
        _grade_catalyst(inputs.snapshot, inputs.now),
        _grade_market(inputs.market_gainers),
    ]
    points = sum(GRADE_POINTS[factor.grade] for factor in factors)
    return SlidingScale(letter=_letter_for(points), points=points, factors=factors)
