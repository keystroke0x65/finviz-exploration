from datetime import datetime, timedelta

import pytest

from app.market_time import EASTERN
from app.setups.resolver import resolve_outcome
from app.setups.store import SetupRecord
from tests.bar_fixtures import daily_bars, make_bar

DETECTED = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)
LATER_SAME_DAY = datetime(2026, 10, 20, 12, 0, tzinfo=EASTERN)


def setup(direction="long", timeframe="1m", detected_at=DETECTED, entry=2.0, stop=1.9, target=2.3):
    return SetupRecord(
        id=1, ticker="HOST", pattern="bull_flag", direction=direction, timeframe=timeframe, entry=entry,
        stop=stop, capped_target=target, target_3r=target, available_reward_risk=3.0, risk_percent=5.0,
        blocking_level=None, partial_1r=0, partial_2r=0, trailing_stop=None, quality=0.7, score=70.0,
        score_parts={}, key_points=[], state="forming", session="regular", float_at_detection=5.0,
        detected_at=detected_at, last_seen_at=detected_at, outcome="open", resolved_at=None,
        max_favorable_r=None, max_adverse_r=None,
    )


def bars_after(*ohlc):
    start = DETECTED
    return [make_bar(9, 59, 2.0, 2.0, 2.0, 2.0)] + [
        make_bar((start + timedelta(minutes=index + 1)).hour, (start + timedelta(minutes=index + 1)).minute, *values)
        for index, values in enumerate(ohlc)
    ]


def test_resolve_target_hit_first():
    bars = bars_after((1.98, 2.02, 1.97, 2.01), (2.01, 2.30, 2.0, 2.28))

    resolution = resolve_outcome(setup(), bars, LATER_SAME_DAY)

    assert resolution.outcome == "target"
    assert resolution.resolved_at == bars[-1].time
    assert resolution.max_favorable_r == pytest.approx(3.0)
    assert resolution.max_adverse_r == pytest.approx(-0.3)


def test_resolve_stop_hit_first():
    bars = bars_after((1.98, 2.05, 1.97, 2.0), (2.0, 2.01, 1.88, 1.89))

    resolution = resolve_outcome(setup(), bars, LATER_SAME_DAY)

    assert resolution.outcome == "stop"
    assert resolution.max_adverse_r == pytest.approx(-1.2)


def test_resolve_same_bar_records_stop():
    bars = bars_after((1.98, 2.35, 1.85, 2.2))

    assert resolve_outcome(setup(), bars, LATER_SAME_DAY).outcome == "stop"


def test_resolve_never_filled_expires_at_eight_pm():
    bars = bars_after((1.95, 1.98, 1.94, 1.96))
    after_close = datetime(2026, 10, 20, 20, 1, tzinfo=EASTERN)

    resolution = resolve_outcome(setup(), bars, after_close)

    assert resolution.outcome == "expired"
    assert resolution.max_favorable_r is None


def test_resolve_still_open_before_deadline():
    bars = bars_after((1.98, 2.05, 1.97, 2.03))

    resolution = resolve_outcome(setup(), bars, LATER_SAME_DAY)

    assert resolution.outcome == "open"
    assert resolution.resolved_at is None


def test_resolve_daily_expires_after_twenty_sessions():
    history = daily_bars([2.0] * 30, start=datetime(2026, 9, 1).date(), spread=0.01)
    record = setup(timeframe="daily", detected_at=history[5].time, entry=2.5, stop=1.5, target=5.5)

    assert resolve_outcome(record, history, history[-1].time).outcome == "expired"
    assert resolve_outcome(record, history[:20], history[19].time).outcome == "open"


def test_resolve_missing_history_is_unresolved():
    later_bars = [make_bar(14, 0, 2.0, 2.4, 1.95, 2.35)]

    assert resolve_outcome(setup(), later_bars, LATER_SAME_DAY).outcome == "unresolved"


def test_short_resolution_mirrors():
    record = setup(direction="short", entry=2.0, stop=2.1, target=1.7)
    bars = bars_after((2.02, 2.03, 1.99, 2.0), (2.0, 2.01, 1.70, 1.72))

    resolution = resolve_outcome(record, bars, LATER_SAME_DAY)

    assert resolution.outcome == "target"
    assert resolution.max_favorable_r == pytest.approx(3.0)
