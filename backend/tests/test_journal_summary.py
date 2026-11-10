from datetime import date, datetime

import pytest

from app.journal.pass_scoring import PassScore
from app.journal.positions import Fill, compute_trade_figures
from app.journal.review import AfterExit
from app.journal.store import EMPTY_FACTS, JournalEntry, SetupSnapshot, StockFacts
from app.journal.summary import ReviewedTrade, ScoredPass, daily_realised_pnl, period_start, summarise
from app.market_time import EASTERN
from app.patterns.sliding_scale import SlidingScale

MONDAY = date(2026, 11, 9)
TUESDAY = date(2026, 11, 10)


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=EASTERN)


NOW = at(TUESDAY, 15)


def setup(pattern="bull_flag", points=10, score=80.0):
    return SetupSnapshot(None, pattern, "1m", "long", 2.0, 1.9, 2.3, 3.0, score, "forming", None,
                         SlidingScale("B", points, []))


def entry(fills, *, kind="trade", mistakes=(), country="USA", pattern="bull_flag", points=10, score=80.0, fees=0.0,
          reasons=(), decided_at=None, plan_stop=1.9, plan_target=2.3, entry_id=1):
    facts = StockFacts(None, country, None, "Software", None, None, None, None, None, None) if country else EMPTY_FACTS
    return JournalEntry(
        kind=kind, ticker="HOST", direction="long", decided_at=decided_at or fills[0].time,
        setup=setup(pattern, points, score) if pattern else None, stock=facts, plan_stop=plan_stop,
        plan_target=plan_target, fees=fees, reasons=list(reasons), mistakes=list(mistakes), note="", pass_price=None,
        fills=fills, id=entry_id, created_at=NOW, updated_at=NOW,
    )


def reviewed(fills, after=None, **kwargs):
    journal_entry = entry(fills, **kwargs)
    figures = compute_trade_figures("long", fills, journal_entry.plan_stop, journal_entry.plan_target,
                                    journal_entry.fees, NOW)
    return ReviewedTrade(journal_entry, figures, after, [])


def round_trip(day, hour, entry_price, exit_price, shares=100, **kwargs):
    return reviewed([Fill("buy", at(day, hour), entry_price, shares), Fill("sell", at(day, hour, 10), exit_price, shares)],
                    **kwargs)


def no_system(pattern, timeframe):
    return None


def test_period_start():
    assert period_start("today", NOW) == at(TUESDAY, 0)
    assert period_start("week", NOW) == at(MONDAY, 0)
    assert period_start("month", NOW) == at(date(2026, 11, 1), 0)
    assert period_start("all", NOW) is None


def test_totals_for_closed_trades():
    trades = [round_trip(TUESDAY, 10, 2.0, 2.5), round_trip(TUESDAY, 11, 2.0, 1.9), round_trip(TUESDAY, 12, 2.0, 2.0)]

    summary = summarise(trades, [], None, no_system)

    assert summary.net_pnl == pytest.approx(40.0)
    assert (summary.trades, summary.wins, summary.losses) == (3, 1, 1)
    assert summary.win_rate == pytest.approx(0.5)
    assert summary.average_gain == pytest.approx(50.0)
    assert summary.average_loss == pytest.approx(-10.0)
    assert (summary.largest_win, summary.largest_loss) == (pytest.approx(50.0), pytest.approx(-10.0))
    assert summary.average_planned_reward_risk == pytest.approx(3.0)
    assert summary.average_duration_seconds == 600


def test_scaling_out_across_days_books_pnl_per_day():
    trade = reviewed([Fill("buy", at(MONDAY, 10), 2.0, 200), Fill("sell", at(MONDAY, 11), 2.5, 100),
                      Fill("sell", at(TUESDAY, 10), 2.2, 100)], fees=4.0)

    today = summarise([trade], [], at(TUESDAY, 0), no_system)
    monday_only = summarise([trade], [], None, no_system)

    assert today.net_pnl == pytest.approx(16.0)
    assert today.trades == 1
    assert monday_only.net_pnl == pytest.approx(66.0)
    assert [point.cumulative for point in monday_only.pnl_points] == pytest.approx([50.0, 66.0])


def test_open_trades_are_counted_separately():
    open_trade = reviewed([Fill("buy", at(TUESDAY, 10), 2.0, 200), Fill("sell", at(TUESDAY, 11), 2.5, 100)])

    summary = summarise([open_trade], [], None, no_system)

    assert (summary.trades, summary.open_trades) == (0, 1)
    assert summary.net_pnl == pytest.approx(50.0)


def test_trades_closed_before_the_period_are_left_out():
    summary = summarise([round_trip(MONDAY, 10, 2.0, 2.5)], [], at(TUESDAY, 0), no_system)

    assert (summary.trades, summary.net_pnl) == (0, 0.0)


def test_breakdowns_count_and_sum_pnl():
    trades = [
        round_trip(TUESDAY, 9, 2.0, 2.5, mistakes=["chased", "oversized"], country="USA"),
        round_trip(TUESDAY, 10, 2.0, 1.9, mistakes=["chased"], country="China", pattern="flat_top_breakout"),
    ]

    summary = summarise(trades, [], None, no_system)

    assert {bucket.label: (bucket.count, bucket.pnl) for bucket in summary.by_mistake} == {
        "chased": (2, pytest.approx(40.0)), "oversized": (1, pytest.approx(50.0))}
    assert {bucket.label: bucket.count for bucket in summary.by_country} == {"USA": 1, "China": 1}
    assert {bucket.label: bucket.count for bucket in summary.by_pattern} == {"bull_flag": 1, "flat_top_breakout": 1}


def test_time_of_day_and_duration_buckets():
    summary = summarise([round_trip(TUESDAY, 9, 2.0, 2.5)], [], None, no_system)
    by_time = {bucket.label: bucket.count for bucket in summary.by_time_of_day}
    by_duration = {bucket.label: bucket.count for bucket in summary.by_duration}

    assert by_time["4:00–9:30"] == 1
    assert by_time["9:30–10"] == 0
    assert by_duration["5–30 min"] == 1


def test_quality_averages():
    trades = [round_trip(TUESDAY, 10, 2.0, 2.5, points=12, score=90.0),
              round_trip(TUESDAY, 11, 2.0, 2.5, points=8, score=70.0, after=AfterExit(1.5, -0.5, 2.6, 2.4))]

    summary = summarise(trades, [], None, no_system)

    assert summary.average_sykes_points == pytest.approx(10.0)
    assert summary.average_sykes_letter == "B"
    assert summary.average_score == pytest.approx(80.0)
    assert summary.average_left_on_table_r == pytest.approx(1.5)


def test_pass_reasons_rows():
    def scored(reasons, outcome, r=None):
        pass_entry = entry([], kind="pass", reasons=reasons, decided_at=at(TUESDAY, 10))
        return ScoredPass(pass_entry, PassScore(outcome, r))

    passes = [scored(["low_sykes"], "stop", -1.0), scored(["low_sykes", "too_late"], "target", 2.0)]

    summary = summarise([], passes, None, no_system)
    rows = {row.reason: row for row in summary.pass_reasons}

    assert summary.passes == 2
    assert (rows["low_sykes"].count, rows["low_sykes"].stop, rows["low_sykes"].target) == (2, 1, 1)
    assert rows["low_sykes"].average_r == pytest.approx(0.5)
    assert rows["too_late"].count == 1


def test_versus_system_rows():
    trades = [round_trip(TUESDAY, 10, 2.0, 2.5), round_trip(TUESDAY, 11, 2.0, 1.9)]

    summary = summarise(trades, [], None, no_system)

    row = summary.versus_system[0]
    assert (row.pattern, row.timeframe, row.trades, row.win_rate) == ("bull_flag", "1m", 2, pytest.approx(0.5))
    assert row.average_r == pytest.approx(2.0)
    assert row.system is None and row.system_has_enough_history is False


def test_daily_realised_pnl_counts_only_todays_closing_fills():
    yesterday = round_trip(MONDAY, 10, 2.0, 2.5)
    split = reviewed([Fill("buy", at(MONDAY, 10), 2.0, 200), Fill("sell", at(MONDAY, 11), 2.5, 100),
                      Fill("sell", at(TUESDAY, 10), 1.8, 100)], fees=5.0)

    assert daily_realised_pnl([yesterday, split], NOW) == pytest.approx(-25.0)
