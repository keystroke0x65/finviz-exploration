from datetime import datetime, timedelta

import pytest

from app.journal.positions import Fill, compute_trade_figures, validate_fills
from app.market_time import EASTERN

START = datetime(2026, 11, 9, 9, 45, tzinfo=EASTERN)
NOW = START + timedelta(hours=3)


def at(minutes: float) -> datetime:
    return START + timedelta(minutes=minutes)


def buy(minutes, price, shares):
    return Fill("buy", at(minutes), price, shares)


def sell(minutes, price, shares):
    return Fill("sell", at(minutes), price, shares)


def test_simple_long_win():
    figures = compute_trade_figures("long", [buy(0, 2.00, 100), sell(10, 2.50, 100)], 1.90, 2.30, 0.0, NOW)

    assert figures.status == "closed"
    assert figures.net_pnl == pytest.approx(50.0)
    assert figures.r_multiple == pytest.approx(5.0)
    assert figures.planned_reward_risk == pytest.approx(3.0)
    assert figures.money_in == pytest.approx(200.0)
    assert figures.duration_seconds == 600


def test_scale_in_and_out_uses_average_cost():
    fills = [buy(0, 2.00, 100), buy(1, 2.20, 100), sell(2, 2.40, 100), sell(3, 2.30, 100)]

    figures = compute_trade_figures("long", fills, None, None, 0.0, NOW)

    assert figures.average_entry == pytest.approx(2.10)
    assert figures.average_exit == pytest.approx(2.35)
    assert figures.realised_pnl == pytest.approx(50.0)
    assert figures.max_shares == 200
    assert figures.money_in == pytest.approx(420.0)
    assert figures.total_bought == pytest.approx(420.0)
    assert [point.pnl for point in figures.closed_pnl] == pytest.approx([30.0, 20.0])
    assert [point.time for point in figures.closed_pnl] == [at(2), at(3)]


def test_fills_are_sorted_by_time():
    figures = compute_trade_figures("long", [sell(10, 2.5, 100), buy(0, 2.0, 100)], None, None, 0.0, NOW)

    assert figures.net_pnl == pytest.approx(50.0)


def test_short_trade_profits_when_price_falls():
    figures = compute_trade_figures("short", [sell(0, 5.0, 100), buy(5, 4.5, 100)], 5.2, 4.4, 0.0, NOW)

    assert figures.net_pnl == pytest.approx(50.0)
    assert figures.r_multiple == pytest.approx(2.5)
    assert figures.planned_reward_risk == pytest.approx(3.0)


def test_open_trade_reports_shares_held_and_no_fees_yet():
    figures = compute_trade_figures("long", [buy(0, 2.0, 100), sell(5, 2.2, 40)], None, None, 2.0, NOW)

    assert figures.status == "open"
    assert figures.shares_held == 60
    assert figures.realised_pnl == pytest.approx(8.0)
    assert figures.net_pnl == pytest.approx(8.0)
    assert figures.duration_seconds == (NOW - START).total_seconds()


def test_fees_reduce_closed_pnl():
    figures = compute_trade_figures("long", [buy(0, 2.0, 100), sell(5, 2.5, 100)], 1.9, None, 3.5, NOW)

    assert figures.net_pnl == pytest.approx(46.5)
    assert figures.r_multiple == pytest.approx(4.65)


def test_no_stop_means_no_r():
    figures = compute_trade_figures("long", [buy(0, 2.0, 100), sell(5, 2.5, 100)], None, 2.6, 0.0, NOW)

    assert figures.r_multiple is None
    assert figures.planned_reward_risk is None


def test_open_trade_without_sells_has_no_exit():
    figures = compute_trade_figures("long", [buy(0, 2.0, 100)], None, None, 0.0, NOW)

    assert figures.average_exit is None
    assert figures.closed_pnl == []


def test_validate_accepts_partial_exits():
    assert validate_fills("long", [buy(0, 2.0, 100), sell(1, 2.1, 50)]) is None


def test_validate_requires_a_fill():
    assert validate_fills("long", []) == "Add at least one fill."


def test_validate_rejects_wrong_opening_side():
    assert validate_fills("long", [sell(0, 2.0, 100)]) == "The first fill must be a buy for a long trade."
    assert validate_fills("short", [buy(0, 2.0, 100)]) == "The first fill must be a sell for a short trade."


def test_validate_rejects_overselling():
    message = validate_fills("long", [buy(0, 2.0, 100), sell(1, 2.1, 150)])

    assert message is not None and "would sell more shares than are held" in message


def test_validate_rejects_overcovering_a_short():
    message = validate_fills("short", [sell(0, 2.0, 100), buy(1, 1.9, 150)])

    assert message is not None and "would buy back more shares than are short" in message


def test_validate_rejects_reentry_after_flat():
    message = validate_fills("long", [buy(0, 2.0, 100), sell(1, 2.1, 100), buy(2, 2.2, 100)])

    assert message == "Shares go back to zero before the last fill; log the rest as a new trade."


def test_validate_rejects_more_than_50_fills():
    fills = [buy(0, 2.0, 100)] + [buy(minute, 2.0, 1) for minute in range(1, 51)]

    assert validate_fills("long", fills) == "A trade can have at most 50 fills."
