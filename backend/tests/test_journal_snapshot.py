from datetime import date, datetime

import pytest

from app.finviz_client import Bar, ScreenRow
from app.journal.snapshot import previous_close, setup_snapshot, stock_facts_at
from app.market_time import EASTERN
from app.patterns.sliding_scale import SlidingScale
from app.setups.store import SetupValues

DAY = date(2026, 11, 9)


def at(hour, minute=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN)


def bar(moment, close, volume=1000):
    return Bar(moment, close, close, close, close, volume)


SNAPSHOT = ScreenRow(
    ticker="HOST", company="Host Corp", country="USA", market_cap_millions=32.4, float_millions=5.5,
    average_volume_thousands=2000.0, relative_volume=4.0, price=2.2, change_percent=10.0, volume=5_000_000,
    after_hours_close=None, after_hours_change_percent=None, news_time=None, news_url=None, news_title=None,
)
QUOTE = {"Company": "Host Corp", "Country": "USA", "Sector": "Technology", "Industry": "Software", "Market Cap": "32.36"}


def test_stock_facts_at_use_bars_up_to_the_moment():
    bars = [bar(at(9, 30), 2.0, 1_000_000), bar(at(9, 45), 2.2, 1_000_000), bar(at(10, 0), 2.5, 9_000_000)]

    facts = stock_facts_at(bars, 2.0, at(9, 50), QUOTE, SNAPSHOT)

    assert facts.price == 2.2
    assert facts.change_percent == pytest.approx(10.0)
    assert facts.volume_so_far == 2_000_000
    assert facts.volume_vs_average == pytest.approx(1.0)
    assert (facts.company, facts.country, facts.sector, facts.industry) == ("Host Corp", "USA", "Technology", "Software")
    assert facts.market_cap_millions == pytest.approx(32.36)
    assert facts.float_millions == 5.5


def test_stock_facts_ignore_earlier_days_volume():
    bars = [bar(at(15, 0, date(2026, 11, 6)), 1.9, 7_000_000), bar(at(9, 30), 2.0, 500)]

    assert stock_facts_at(bars, 1.9, at(9, 31), None, None).volume_so_far == 500


def test_stock_facts_without_data_are_empty():
    facts = stock_facts_at([], None, at(9, 30), None, None)

    assert (facts.price, facts.change_percent, facts.volume_so_far, facts.company) == (None, None, None, None)


def test_unparseable_market_cap_is_none():
    assert stock_facts_at([], None, at(9, 30), {**QUOTE, "Market Cap": "-"}, None).market_cap_millions is None


def test_previous_close_is_last_daily_close_before_the_day():
    daily = [bar(at(0, 0, date(2026, 11, 5)), 1.5), bar(at(0, 0, date(2026, 11, 6)), 1.8), bar(at(0, 0), 2.4)]

    assert previous_close(daily, DAY) == 1.8
    assert previous_close([], DAY) is None


def test_setup_snapshot_uses_values_at_the_time(db_conn):
    from tests.test_setup_store import record

    saved = record(db_conn)
    grade = SlidingScale("B", 10, [])

    snapshot = setup_snapshot(saved, SetupValues(88.0, "triggered", "leans_long", grade))

    assert (snapshot.setup_record_id, snapshot.pattern, snapshot.entry, snapshot.stop, snapshot.target) == (
        saved.id, "bull_flag", 2.0, 1.9, 2.15)
    assert (snapshot.score, snapshot.state, snapshot.verdict, snapshot.sliding_scale) == (88.0, "triggered", "leans_long", grade)
    assert snapshot.reward_risk == 1.5
