from dataclasses import replace
from datetime import datetime

from app.market_time import EASTERN
from app.patterns.sliding_scale import MarketGainers
from app.scanning.market_gainers import count_big_gainers, read_market_gainers, save_market_gainers
from tests.scan_fixtures import snapshot

MORNING = datetime(2026, 10, 20, 10, 0, tzinfo=EASTERN)
PRE_MARKET = datetime(2026, 10, 20, 7, 0, tzinfo=EASTERN)


def test_counts_stocks_up_30_percent_or_more():
    rows = [replace(snapshot(ticker), change_percent=change) for ticker, change in
            [("AAA", 30.0), ("BBB", 145.7), ("CCC", 29.9), ("DDD", None)]]

    assert count_big_gainers(rows) == 2


def test_reads_back_todays_count(db_conn):
    save_market_gainers(db_conn, 12, MORNING)

    assert read_market_gainers(db_conn, MORNING.replace(hour=11)) == MarketGainers(count=12, is_previous_session=False)


def test_a_pre_market_count_is_the_previous_sessions(db_conn):
    save_market_gainers(db_conn, 4, PRE_MARKET)

    assert read_market_gainers(db_conn, PRE_MARKET.replace(hour=8)) == MarketGainers(count=4, is_previous_session=True)


def test_yesterdays_count_is_not_used(db_conn):
    save_market_gainers(db_conn, 12, MORNING)

    assert read_market_gainers(db_conn, MORNING.replace(day=21)) is None


def test_no_count_yet(db_conn):
    assert read_market_gainers(db_conn, MORNING) is None
