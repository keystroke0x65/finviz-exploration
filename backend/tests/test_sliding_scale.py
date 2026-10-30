from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from app.finviz_client import Bar
from app.market_time import EASTERN
from app.patterns.sliding_scale import (
    MarketGainers,
    SlidingScaleInputs,
    count_spike_days,
    grade_sliding_scale,
)
from tests.scan_fixtures import snapshot

NOW = datetime(2026, 10, 20, 9, 45, tzinfo=EASTERN)

# Good on every factor.
BEST = SlidingScaleInputs(
    quality=0.8,
    state="triggered",
    reward_risk=3.0,
    snapshot=replace(snapshot("HOST", news_time=NOW - timedelta(hours=2)), volume=4_200_000),
    spike_days=4,
    setup_time=NOW,
    market_gainers=MarketGainers(count=12, is_previous_session=False),
    now=NOW,
)


def factor(inputs: SlidingScaleInputs, name: str):
    return next(item for item in grade_sliding_scale(inputs).factors if item.name == name)


def test_a_setup_good_on_every_factor_gets_an_a_with_full_points():
    scale = grade_sliding_scale(BEST)

    assert scale.letter == "A"
    assert scale.points == 14
    assert [item.name for item in scale.factors] == [
        "Pattern & price", "Risk/reward", "Entry/exit ease", "Past spikes", "Time", "Catalyst", "Market",
    ]
    assert all(item.grade == "good" for item in scale.factors)


@pytest.mark.parametrize(
    ("points_lost", "letter"),
    [(2, "A"), (3, "B"), (4, "B"), (5, "C"), (6, "C"), (7, "D"), (8, "D"), (9, "F")],
)
def test_grade_letters_step_every_two_points(points_lost, letter):
    # Each factor dropped from good to poor costs two points; to ok, one.
    poor = [
        dict(reward_risk=1.5), dict(spike_days=0), dict(setup_time=NOW.replace(hour=7)),
        dict(market_gainers=MarketGainers(count=1, is_previous_session=False)),
    ]
    changes: dict = {}
    for change in poor[: points_lost // 2]:
        changes.update(change)
    if points_lost % 2:
        changes["quality"] = 0.5
    assert grade_sliding_scale(replace(BEST, **changes)).letter == letter


def test_pattern_and_price_wants_a_clean_pattern_not_yet_extended():
    assert factor(replace(BEST, quality=0.5), "Pattern & price").grade == "ok"
    assert factor(replace(BEST, state="extended"), "Pattern & price").grade == "ok"
    extended_and_weak = factor(replace(BEST, quality=0.5, state="extended"), "Pattern & price")
    assert extended_and_weak.grade == "poor"
    assert extended_and_weak.detail == "Quality 0.50, extended past entry"


@pytest.mark.parametrize(("reward_risk", "grade"), [(3.0, "good"), (2.5, "ok"), (2.0, "poor"), (1.2, "poor")])
def test_risk_reward_wants_3r_and_calls_2r_not_enough(reward_risk, grade):
    graded = factor(replace(BEST, reward_risk=reward_risk), "Risk/reward")
    assert graded.grade == grade
    assert graded.detail == f"{reward_risk:.1f}R (wants 3R+)"


def test_entry_exit_ease_uses_the_larger_of_todays_and_average_volume():
    thin_today = replace(BEST.snapshot, volume=200_000, average_volume_thousands=1_500.0)
    assert factor(replace(BEST, snapshot=thin_today), "Entry/exit ease").grade == "good"

    middling = replace(BEST.snapshot, volume=600_000, average_volume_thousands=300.0)
    graded = factor(replace(BEST, snapshot=middling), "Entry/exit ease")
    assert graded.grade == "ok"
    assert graded.detail == "600K shares today, 300K average"

    thin = replace(BEST.snapshot, volume=90_000, average_volume_thousands=120.0)
    assert factor(replace(BEST, snapshot=thin), "Entry/exit ease").grade == "poor"


def test_missing_data_counts_as_neutral_and_says_so():
    scale = grade_sliding_scale(replace(BEST, snapshot=None, spike_days=None, market_gainers=None))

    missing = [item for item in scale.factors if item.grade == "no_data"]
    assert [item.name for item in missing] == ["Entry/exit ease", "Past spikes", "Catalyst", "Market"]
    assert scale.points == 14 - 4  # each missing factor counts 1 of its 2 points


@pytest.mark.parametrize(("spike_days", "grade"), [(3, "good"), (2, "ok"), (1, "ok"), (0, "poor")])
def test_past_spikes_grades_how_often_the_stock_has_spiked(spike_days, grade):
    graded = factor(replace(BEST, spike_days=spike_days), "Past spikes")
    assert graded.grade == grade
    assert graded.detail == f"{spike_days} days up 30%+ in the past year"


@pytest.mark.parametrize(
    ("hour", "minute", "grade", "detail"),
    [
        (9, 30, "good", "Power hour (9:30 AM)"),
        (10, 29, "good", "Power hour (10:29 AM)"),
        (10, 30, "ok", "Midday (10:30 AM)"),
        (14, 59, "ok", "Midday (2:59 PM)"),
        (15, 0, "good", "Power hour (3:00 PM)"),
        (16, 0, "poor", "After-hours (4:00 PM)"),
        (7, 5, "poor", "Pre-market (7:05 AM)"),
    ],
)
def test_time_prefers_the_first_and_last_hour(hour, minute, grade, detail):
    graded = factor(replace(BEST, setup_time=NOW.replace(hour=hour, minute=minute)), "Time")
    assert (graded.grade, graded.detail) == (grade, detail)


def test_catalyst_wants_fresh_news():
    def news_at(moment):
        return replace(BEST, snapshot=replace(BEST.snapshot, news_time=moment))

    assert factor(news_at(NOW - timedelta(hours=23)), "Catalyst").grade == "good"
    two_days_old = factor(news_at(NOW - timedelta(days=2)), "Catalyst")
    assert two_days_old.grade == "ok"
    assert two_days_old.detail == "News Oct 18, 9:45 AM (over 24 hours ago)"
    stale = factor(news_at(NOW - timedelta(days=4)), "Catalyst")
    assert (stale.grade, stale.detail) == ("poor", "No news in the last 3 days")
    assert factor(news_at(None), "Catalyst").grade == "poor"


@pytest.mark.parametrize(("count", "grade"), [(10, "good"), (9, "ok"), (5, "ok"), (4, "poor")])
def test_market_counts_big_gainers(count, grade):
    graded = factor(replace(BEST, market_gainers=MarketGainers(count=count, is_previous_session=False)), "Market")
    assert graded.grade == grade
    assert graded.detail == f"{count} US stocks up 30%+ today"


def test_market_says_when_the_count_is_from_the_previous_session():
    graded = factor(replace(BEST, market_gainers=MarketGainers(count=3, is_previous_session=True)), "Market")
    assert graded.detail == "3 US stocks up 30%+ in the previous session"


def bar(day: int, close: float, high: float | None = None, month: int = 10, year: int = 2026) -> Bar:
    return Bar(datetime(year, month, day, tzinfo=EASTERN), close, high or close, close, close, 1000)


def test_spike_days_count_highs_30_percent_over_the_previous_close():
    bars = [
        bar(1, 1.00), bar(2, 1.10, high=1.31),  # spike: high 31% over 1.00
        bar(5, 1.00, high=1.45),                # spike: 32% over 1.10
        bar(6, 1.00, high=1.29),                # not quite 30%
        bar(7, 1.00),
    ]
    assert count_spike_days(bars, today=date(2026, 10, 20)) == 2


def test_spike_days_skip_today_and_anything_older_than_a_year():
    bars = [
        bar(1, 1.00, year=2025), bar(2, 1.00, high=2.00, year=2025),  # over a year ago
        bar(19, 1.00), bar(20, 1.00, high=2.00),                     # today
    ]
    assert count_spike_days(bars, today=date(2026, 10, 20)) == 0
