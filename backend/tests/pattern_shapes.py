"""Builds bar series from explicit highs/lows for pattern tests."""

from datetime import datetime, timedelta

from app.finviz_client import Bar
from app.market_time import EASTERN

START = datetime(2026, 10, 20, 9, 30, tzinfo=EASTERN)


def shape(highs: list[float], lows: list[float], volumes: list[int] | None = None,
          last_close: float | None = None, step_minutes: int = 1, start: datetime = START) -> list[Bar]:
    volumes = volumes or [1000] * len(highs)
    bars = [
        Bar(start + timedelta(minutes=index * step_minutes), (high + low) / 2, high, low, (high + low) / 2, volume)
        for index, (high, low, volume) in enumerate(zip(highs, lows, volumes))
    ]
    if last_close is not None:
        last = bars[-1]
        bars[-1] = Bar(last.time, last.open, max(last.high, last_close), min(last.low, last_close), last_close,
                       last.volume)
    return bars


def mirrored(highs: list[float], lows: list[float], pivot: float = 5.0) -> tuple[list[float], list[float]]:
    """Flips a shape upside down (price -> pivot - price) to build bearish twins."""
    return [pivot - low for low in lows], [pivot - high for high in highs]


def zigzag(pivots: list[float], steps: int = 3, spread: float = 0.01, volume: int = 1000,
           step_minutes: int = 1, start: datetime = START) -> list[Bar]:
    """Bars walking in straight lines between turning points, `steps` bars per leg.

    Each bar's high/low sit `spread` around its close, so every interior pivot
    becomes a swing high or low."""
    closes: list[float] = [pivots[0]]
    for begin, end in zip(pivots, pivots[1:]):
        closes += [begin + (end - begin) * step / steps for step in range(1, steps + 1)]
    bars = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        bars.append(Bar(start + timedelta(minutes=index * step_minutes), previous,
                        max(previous, close) + spread, min(previous, close) - spread, close, volume))
    return bars
