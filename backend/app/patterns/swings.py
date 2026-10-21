"""Swing highs and lows: the turning points several patterns are built from."""

from dataclasses import dataclass

from app.finviz_client import Bar

DEFAULT_SIDE_BARS = 2


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    is_high: bool


def find_swings(bars: list[Bar], side_bars: int = DEFAULT_SIDE_BARS) -> list[Swing]:
    """A swing high's high is strictly above the highs of `side_bars` bars on each side
    (swing lows likewise); bars without a full window on both sides are skipped."""
    swings: list[Swing] = []
    for index in range(side_bars, len(bars) - side_bars):
        neighbours = bars[index - side_bars : index] + bars[index + 1 : index + 1 + side_bars]
        bar = bars[index]
        if all(bar.high > other.high for other in neighbours):
            swings.append(Swing(index, bar.high, True))
        if all(bar.low < other.low for other in neighbours):
            swings.append(Swing(index, bar.low, False))
    return swings
