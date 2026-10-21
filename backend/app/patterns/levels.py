"""Daily support/resistance levels: a stand-in for the lines a trader draws by hand.

Swing highs and lows from about two years of daily bars are clustered, and any
price the stock turned at more than once becomes a level.
"""

from dataclasses import dataclass

from app.finviz_client import Bar

LEVEL_LOOKBACK_BARS = 504  # about two years of trading days
SWING_WINDOW = 5
MERGE_TOLERANCE_PERCENT = 1.5
MIN_TOUCHES = 2


@dataclass(frozen=True)
class PriceLevel:
    price: float
    touches: int


def _swing_prices(bars: list[Bar]) -> list[float]:
    # Strictly beyond every neighbour, so a flat stretch of equal highs isn't
    # read as a row of separate turning points.
    prices: list[float] = []
    for index in range(SWING_WINDOW, len(bars) - SWING_WINDOW):
        neighbours = bars[index - SWING_WINDOW : index] + bars[index + 1 : index + 1 + SWING_WINDOW]
        bar = bars[index]
        if all(bar.high > other.high for other in neighbours):
            prices.append(bar.high)
        if all(bar.low < other.low for other in neighbours):
            prices.append(bar.low)
    return prices


def _cluster(prices: list[float]) -> list[list[float]]:
    clusters: list[list[float]] = []
    for price in sorted(prices):
        if clusters:
            cluster = clusters[-1]
            mean = sum(cluster) / len(cluster)
            if abs(price - mean) / mean * 100 <= MERGE_TOLERANCE_PERCENT:
                cluster.append(price)
                continue
        clusters.append([price])
    return clusters


def find_daily_levels(daily_bars: list[Bar]) -> list[PriceLevel]:
    recent = daily_bars[-LEVEL_LOOKBACK_BARS:]
    return [
        PriceLevel(price=sum(cluster) / len(cluster), touches=len(cluster))
        for cluster in _cluster(_swing_prices(recent))
        if len(cluster) >= MIN_TOUCHES
    ]


def nearest_level_above(levels: list[PriceLevel], price: float) -> PriceLevel | None:
    above = [level for level in levels if level.price > price]
    return min(above, key=lambda level: level.price) if above else None


def nearest_level_below(levels: list[PriceLevel], price: float) -> PriceLevel | None:
    below = [level for level in levels if level.price < price]
    return max(below, key=lambda level: level.price) if below else None
