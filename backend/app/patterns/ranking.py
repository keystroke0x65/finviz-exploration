"""Scores a setup 0-100 from parts that are all shown to the user."""

from dataclasses import dataclass

from app.patterns.trade_plan import TARGET_R, TradePlan
from app.patterns.types import TIMEFRAME_ORDER, PatternMatch, SetupState

WEIGHTS = {
    "reward_risk": 0.40,
    "quality": 0.25,
    "volume": 0.15,
    "freshness": 0.10,
    "timeframe_agreement": 0.10,
}
CONFLICT_PENALTY = 0.20
FULL_VOLUME_RELATIVE = 3.0
EXTENDED_FRESHNESS = 0.3
SCALE = 100


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    # Each part is already weighted and in points, so the parts add up to the total.
    parts: dict[str, float]


def _has_agreement(match: PatternMatch, others: list[PatternMatch]) -> bool:
    return any(other.direction == match.direction and other.timeframe != match.timeframe for other in others)


def _has_conflict(match: PatternMatch, others: list[PatternMatch]) -> bool:
    rank = TIMEFRAME_ORDER[match.timeframe]
    return any(
        other.direction != match.direction and TIMEFRAME_ORDER[other.timeframe] >= rank for other in others
    )


def score_setup(
    match: PatternMatch,
    plan: TradePlan,
    state: SetupState,
    relative_volume: float | None,
    other_matches: list[PatternMatch],
) -> ScoreBreakdown:
    raw = {
        "reward_risk": min(plan.available_reward_risk, TARGET_R) / TARGET_R,
        "quality": match.quality,
        "volume": min((relative_volume or 0) / FULL_VOLUME_RELATIVE, 1.0),
        "freshness": EXTENDED_FRESHNESS if state == "extended" else 1.0,
        "timeframe_agreement": 1.0 if _has_agreement(match, other_matches) else 0.0,
    }
    parts = {name: round(WEIGHTS[name] * value * SCALE, 1) for name, value in raw.items()}
    parts["conflict"] = -CONFLICT_PENALTY * SCALE if _has_conflict(match, other_matches) else 0.0
    total = round(min(max(sum(parts.values()), 0.0), SCALE), 1)
    return ScoreBreakdown(total=total, parts=parts)
