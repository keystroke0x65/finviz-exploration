"""What a stock and its setup looked like at the moment the user traded or passed."""

from datetime import date, datetime

from app.finviz_client import Bar, ScreenRow
from app.journal.store import SetupSnapshot, StockFacts
from app.market_time import EASTERN
from app.setups.store import SetupRecord, SetupValues

THOUSAND = 1000


def _parse_float(raw: object) -> float | None:
    """Finviz quote values arrive as strings and use '-' for missing."""
    if raw is None:
        return None
    try:
        return float(str(raw).rstrip("%").replace(",", ""))
    except ValueError:
        return None


def _text(quote: dict | None, key: str) -> str | None:
    value = None if quote is None else quote.get(key)
    return None if value in (None, "", "-") else str(value)


def previous_close(daily_bars: list[Bar], day: date) -> float | None:
    earlier = [bar for bar in daily_bars if bar.time.astimezone(EASTERN).date() < day]
    return max(earlier, key=lambda bar: bar.time).close if earlier else None


def stock_facts_at(
    bars: list[Bar],
    previous_close_price: float | None,
    at: datetime,
    quote: dict | None,
    snapshot_row: ScreenRow | None,
) -> StockFacts:
    """Price, change and volume from the bars up to `at`; the slow-moving facts from the quote.

    Finviz's own relative volume is a live figure, so volume vs. average is
    worked out from the bars instead, unscaled for time of day.
    """
    day = at.astimezone(EASTERN).date()
    so_far = [bar for bar in bars if bar.time <= at and bar.time.astimezone(EASTERN).date() == day]
    price = so_far[-1].close if so_far else None
    volume = sum(bar.volume for bar in so_far) if so_far else None
    average_volume = snapshot_row.average_volume_thousands if snapshot_row else None
    return StockFacts(
        company=_text(quote, "Company") or (snapshot_row.company if snapshot_row else None),
        country=_text(quote, "Country") or (snapshot_row.country if snapshot_row else None),
        sector=_text(quote, "Sector"),
        industry=_text(quote, "Industry"),
        market_cap_millions=_parse_float(quote.get("Market Cap")) if quote else (
            snapshot_row.market_cap_millions if snapshot_row else None),
        float_millions=snapshot_row.float_millions if snapshot_row else None,
        price=price,
        change_percent=(price / previous_close_price - 1) * 100 if price and previous_close_price else None,
        volume_so_far=volume,
        volume_vs_average=volume / (average_volume * THOUSAND) if volume is not None and average_volume else None,
    )


def setup_snapshot(record: SetupRecord, values: SetupValues | None) -> SetupSnapshot:
    current = values or SetupValues(record.score, record.state, record.verdict, record.sliding_scale)
    return SetupSnapshot(
        setup_record_id=record.id,
        pattern=record.pattern,
        timeframe=record.timeframe,
        direction=record.direction,
        entry=record.entry,
        stop=record.stop,
        target=record.capped_target,
        reward_risk=record.available_reward_risk,
        score=current.score,
        state=current.state,
        verdict=current.verdict,
        sliding_scale=current.sliding_scale,
    )
