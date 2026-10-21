from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.finviz_client import Interval
from app.patterns.levels import PriceLevel

Direction = Literal["long", "short"]
SetupState = Literal["forming", "triggered", "extended", "invalidated"]
TIMEFRAME_ORDER = {"1m": 0, "5m": 1, "daily": 2}


@dataclass(frozen=True)
class SessionLevels:
    premarket_high: float | None
    premarket_low: float | None
    day_high: float | None
    day_low: float | None
    opening_range_high: float | None
    opening_range_low: float | None
    previous_close: float | None


@dataclass(frozen=True)
class PatternMatch:
    pattern: str
    direction: Direction
    timeframe: Interval
    entry: float
    stop: float
    detected_at: datetime
    quality: float
    quality_parts: dict[str, float]
    # (time, price) points that outline the pattern on a chart.
    key_points: list[tuple[datetime, float]]


@dataclass(frozen=True)
class DetectorContext:
    timeframe: Interval
    daily_levels: list[PriceLevel]
    # None for daily bars; `vwap` is aligned one-to-one with the bar list.
    session: SessionLevels | None
    vwap: list[float | None] | None
