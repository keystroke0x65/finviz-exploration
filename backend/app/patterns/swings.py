"""Swing highs and lows: the turning points several patterns are built from."""

from dataclasses import dataclass

from app.finviz_client import Bar

DEFAULT_SIDE_BARS = 2


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    is_high: bool


def _plateau_swings(values: list[float], side_bars: int, is_high: bool) -> list[Swing]:
    swings: list[Swing] = []
    index = 0
    while index < len(values):
        # Equal consecutive extremes (common on penny-tick stocks and 1m bars)
        # form one plateau, reported once at its first bar.
        end = index
        while end + 1 < len(values) and values[end + 1] == values[index]:
            end += 1
        if index >= side_bars and end + side_bars < len(values):
            neighbours = values[index - side_bars : index] + values[end + 1 : end + 1 + side_bars]
            beyond = (lambda other: values[index] > other) if is_high else (lambda other: values[index] < other)
            if all(beyond(other) for other in neighbours):
                swings.append(Swing(index, values[index], is_high))
        index = end + 1
    return swings


def find_swings(bars: list[Bar], side_bars: int = DEFAULT_SIDE_BARS) -> list[Swing]:
    """Swing highs: a high (or a run of equal highs) strictly above the `side_bars`
    highs on each side; swing lows likewise. Bars without a full window on both
    sides are skipped. Ordered by index, a high before a low at the same bar."""
    highs = _plateau_swings([bar.high for bar in bars], side_bars, True)
    lows = _plateau_swings([bar.low for bar in bars], side_bars, False)
    return sorted(highs + lows, key=lambda swing: (swing.index, not swing.is_high))
