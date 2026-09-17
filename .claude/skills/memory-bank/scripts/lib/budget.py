"""Size budgets. Keep these in sync with references/spec.md.

A memory bank that grows without limit stops being read, so budgets turn
growth into a signal to consolidate (ACE's grow-and-refine).
"""
from __future__ import annotations

from typing import List

CONTENT_MIN = 12
CONTENT_MAX = 400
WHEN_MAX = 120
MAX_DELTA_DEPTH = 3            # DeltaMem MAX_DEPTH
PROMOTE_MIN_HELPFUL = 3        # DeltaMem CONSOLIDATION_THRESHOLD
PRUNE_MIN_HARMFUL = 2
DUPLICATE_THRESHOLD = 0.82     # reject ADD above this similarity
NEAR_DUPLICATE_REPORT = 0.6    # report in consolidate above this
STALE_DAYS = 90
ACTIVE_CONTEXT_MAX_LINES = 80
DONE_SECTION_MAX = 15
TOTAL_CHARS_WARN = 60_000      # roughly 15k tokens across entry files

FILE_LIMITS = {
    "context": {"entries": 60, "chars": 9_000},
    "experience": {"entries": 80, "chars": 12_000},
    "progress": {"entries": 50, "chars": 7_000},
}


def limits_for(relpath: str) -> dict:
    if relpath.startswith("context/"):
        return FILE_LIMITS["context"]
    if relpath.startswith("experience/"):
        return FILE_LIMITS["experience"]
    return FILE_LIMITS["progress"]


def file_warnings(relpath: str, n_entries: int, n_chars: int) -> List[str]:
    lim = limits_for(relpath)
    out = []
    if n_entries > lim["entries"]:
        out.append(f"{relpath}: {n_entries} entries exceeds budget {lim['entries']} — run consolidate")
    if n_chars > lim["chars"]:
        out.append(f"{relpath}: {n_chars} chars exceeds budget {lim['chars']} — run consolidate")
    return out
