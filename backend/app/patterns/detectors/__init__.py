"""Pattern detector registry.

Every detector is a plain function `(bars, context) -> list[PatternMatch]`
registered with the timeframes it runs on. Adding a pattern means writing one
function (plus tests) and listing it here.
"""

from typing import Callable

from app.finviz_client import Bar, Interval
from app.patterns.detectors.doubles import DOUBLE_DETECTORS
from app.patterns.detectors.flags import FLAG_DETECTORS
from app.patterns.detectors.flat_levels import FLAT_LEVEL_DETECTORS
from app.patterns.detectors.level_breaks import LEVEL_BREAK_DETECTORS
from app.patterns.detectors.triangles import TRIANGLE_DETECTORS
from app.patterns.types import DetectorContext, PatternMatch

Detector = Callable[[list[Bar], DetectorContext], list[PatternMatch]]

DETECTORS: list[tuple[Detector, frozenset[Interval]]] = [
    *LEVEL_BREAK_DETECTORS,
    *FLAG_DETECTORS,
    *FLAT_LEVEL_DETECTORS,
    *TRIANGLE_DETECTORS,
    *DOUBLE_DETECTORS,
]


def run_detectors(bars: list[Bar], context: DetectorContext) -> list[PatternMatch]:
    return [
        match
        for detector, timeframes in DETECTORS
        if context.timeframe in timeframes
        for match in detector(bars, context)
    ]
