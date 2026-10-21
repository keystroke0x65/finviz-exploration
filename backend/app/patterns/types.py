from dataclasses import dataclass
from typing import Literal

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
