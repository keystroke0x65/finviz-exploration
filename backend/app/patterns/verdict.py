"""One call per stock: leans long, leans short, or no clear edge, with the reasons.

Patterns are one input; trend, volume and room to the nearest daily levels are the
others. "No clear edge" is an honest, common answer and is never forced into a call.
"""

from dataclasses import dataclass
from typing import Literal

from app.finviz_client import Bar
from app.patterns.indicators import ema, sma
from app.patterns.levels import PriceLevel, nearest_level_above, nearest_level_below
from app.patterns.types import PatternMatch

VerdictCall = Literal["leans_long", "leans_short", "no_clear_edge"]

WEIGHTS = {"trend": 0.35, "patterns": 0.30, "volume": 0.20, "location": 0.15}
CALL_THRESHOLD = 0.25
VOLUME_LOOKBACK_BARS = 20
# Room on each side is capped (and a side with no level counts as the cap), so a
# distant support doesn't read as bearish for a stock with blue sky overhead.
MAX_LEVEL_ROOM = 0.20
# Below this much available weight (e.g. only patterns, or only the daily trend)
# there isn't enough evidence for a call.
MIN_WEIGHT_FOR_CALL = 0.5
# Trend and patterns pulling hard in opposite directions is a mixed picture.
STRONG_DISAGREEMENT = 0.5
# Relative volume at or above this gives the volume balance full weight.
FULL_RELATIVE_VOLUME = 1.5
NOT_ENOUGH_DATA = "Not enough data for a call"
DISAGREEMENT = "Trend and patterns disagree"
MIXED_BAND = 0.2
FAST_EMA, SLOW_EMA = 9, 20
SHORT_SMA, LONG_SMA = 20, 50

MISSING_REASONS = {
    "trend": "No trend data",
    "volume": "No intraday volume data",
    "location": "No daily support/resistance levels",
    "patterns": "No patterns detected",
}


@dataclass(frozen=True)
class Verdict:
    call: VerdictCall
    score: float
    parts: dict[str, float]
    reasons: list[str]


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def _last_close_vs(bars: list[Bar], averages: list[float | None]) -> list[int]:
    if not bars or averages[-1] is None:
        return []
    return [_sign(bars[-1].close - averages[-1])]


def _trend_signals(one_minute: list[Bar], five_minute: list[Bar], daily: list[Bar],
                   vwap: list[float | None] | None) -> list[int]:
    signals: list[int] = []
    if one_minute and vwap:
        signals += _last_close_vs(one_minute, vwap)
    for bars in (one_minute, five_minute):
        closes = [bar.close for bar in bars]
        for period in (FAST_EMA, SLOW_EMA):
            signals += _last_close_vs(bars, ema(closes, period)) if bars else []
    daily_closes = [bar.close for bar in daily]
    for period in (SHORT_SMA, LONG_SMA):
        signals += _last_close_vs(daily, sma(daily_closes, period)) if daily else []
    return signals


def _volume_balance(one_minute: list[Bar]) -> float | None:
    recent = one_minute[-VOLUME_LOOKBACK_BARS:]
    up = sum(bar.volume for bar in recent if bar.close > bar.open)
    down = sum(bar.volume for bar in recent if bar.close < bar.open)
    return (up - down) / (up + down) if up + down else None


def _location(price: float | None, levels: list[PriceLevel]) -> tuple[float, str] | None:
    if price is None or not levels:
        return None
    above, below = nearest_level_above(levels, price), nearest_level_below(levels, price)
    up_room = (above.price - price) / price if above else MAX_LEVEL_ROOM
    down_room = (price - below.price) / price if below else MAX_LEVEL_ROOM
    capped_up, capped_down = min(up_room, MAX_LEVEL_ROOM), min(down_room, MAX_LEVEL_ROOM)
    value = (capped_up - capped_down) / (capped_up + capped_down)
    above_text = f"resistance {above.price:.2f} (+{up_room:.0%})" if above else "no resistance overhead"
    below_text = f"support {below.price:.2f} (-{down_room:.0%})" if below else "no support below"
    return value, f"Room: {above_text}, {below_text}"


def _pattern_balance(matches: list[PatternMatch]) -> tuple[float, str] | None:
    total = sum(match.quality for match in matches)
    if not matches or total == 0:
        return None
    longs = [match for match in matches if match.direction == "long"]
    shorts = [match for match in matches if match.direction == "short"]
    value = (sum(m.quality for m in longs) - sum(m.quality for m in shorts)) / total
    return value, f"{len(longs)} bullish pattern{'s' if len(longs) != 1 else ''}, {len(shorts)} bearish"


def _trend_reason(signals: list[int]) -> str:
    above = sum(1 for signal in signals if signal > 0)
    if above * 2 >= len(signals):
        return f"Above {above} of {len(signals)} trend lines (VWAP, 9/20 EMAs, 20/50-day averages)"
    return f"Below {len(signals) - above} of {len(signals)} trend lines (VWAP, 9/20 EMAs, 20/50-day averages)"


def _volume_reason(value: float) -> str:
    if value > MIXED_BAND:
        return "Volume heavier on up bars"
    if value < -MIXED_BAND:
        return "Volume heavier on down bars"
    return "Volume balanced between up and down bars"


def _caveat(parts: dict[str, float], total_weight: float) -> str | None:
    """Why the evidence can't support a call, if it can't."""
    if total_weight < MIN_WEIGHT_FOR_CALL:
        return NOT_ENOUGH_DATA
    trend, patterns = parts.get("trend"), parts.get("patterns")
    if (
        trend is not None
        and patterns is not None
        and trend * patterns < 0
        and min(abs(trend), abs(patterns)) >= STRONG_DISAGREEMENT
    ):
        return DISAGREEMENT
    return None


def compute_verdict(
    intraday_1m: list[Bar],
    intraday_5m: list[Bar],
    daily: list[Bar],
    vwap_1m: list[float | None] | None,
    daily_levels: list[PriceLevel],
    matches: list[PatternMatch],
    relative_volume: float | None = None,
) -> Verdict:
    parts: dict[str, float] = {}
    part_reasons: dict[str, str] = {}

    signals = _trend_signals(intraday_1m, intraday_5m, daily, vwap_1m)
    if signals:
        parts["trend"] = sum(signals) / len(signals)
        part_reasons["trend"] = _trend_reason(signals)

    volume = _volume_balance(intraday_1m)
    if volume is not None:
        reason = _volume_reason(volume)
        if relative_volume is not None:
            # Up/down balance on thin trading says less than on heavy trading.
            volume *= min(relative_volume / FULL_RELATIVE_VOLUME, 1.0)
            reason += f" on {relative_volume:.1f}x relative volume"
        parts["volume"] = volume
        part_reasons["volume"] = reason

    latest = next((bars[-1].close for bars in (intraday_1m, intraday_5m, daily) if bars), None)
    location = _location(latest, daily_levels)
    if location is not None:
        parts["location"], part_reasons["location"] = location

    pattern_balance = _pattern_balance(matches)
    if pattern_balance is not None:
        parts["patterns"], part_reasons["patterns"] = pattern_balance

    total_weight = sum(WEIGHTS[name] for name in parts)
    score = sum(WEIGHTS[name] * value for name, value in parts.items()) / total_weight if total_weight else 0.0
    caveat = _caveat(parts, total_weight)
    if caveat is None and score >= CALL_THRESHOLD:
        call: VerdictCall = "leans_long"
    elif caveat is None and score <= -CALL_THRESHOLD:
        call = "leans_short"
    else:
        call = "no_clear_edge"

    ordered = sorted(parts, key=lambda name: abs(WEIGHTS[name] * parts[name]), reverse=True)
    reasons = ([caveat] if caveat else []) + [part_reasons[name] for name in ordered] + [
        MISSING_REASONS[name] for name in WEIGHTS if name not in parts
    ]
    return Verdict(call=call, score=round(score, 3), parts=parts, reasons=reasons)
