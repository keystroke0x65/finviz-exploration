"""How far the running watchlist scan has got, for the Setups tab's progress bar.

Kept in memory: the app is one process and scans already take a process-wide lock, so
there's at most one scan to describe, and nothing about it needs to outlive a restart.
"""

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

ScanKind = Literal["manual", "automatic"]
# preparing: watchlist prices and picking active stocks; scanning: one stock at a time;
# finishing: settling setups of stocks that dropped out of the active set.
ScanPhase = Literal["preparing", "scanning", "finishing"]


@dataclass(frozen=True)
class ScanProgress:
    kind: ScanKind
    phase: ScanPhase
    done: int
    total: int
    ticker: str | None
    started_at: datetime


class ProgressTracker:
    """Written by the scan's thread, read by request threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress: ScanProgress | None = None

    def _update(self, **changes: object) -> None:
        with self._lock:
            # Reporting outside a started scan (e.g. a one-stock scan) changes nothing.
            if self._progress is not None:
                self._progress = replace(self._progress, **changes)

    def start(self, kind: ScanKind, started_at: datetime) -> None:
        with self._lock:
            self._progress = ScanProgress(kind, "preparing", 0, 0, None, started_at)

    def set_total(self, total: int) -> None:
        self._update(total=total)

    def set_phase(self, phase: ScanPhase) -> None:
        if phase == "finishing":
            with self._lock:
                if self._progress is not None:
                    self._progress = replace(self._progress, phase=phase, done=self._progress.total, ticker=None)
            return
        self._update(phase=phase)

    def begin_ticker(self, ticker: str, index: int) -> None:
        self._update(ticker=ticker, done=index)

    def finish(self) -> None:
        with self._lock:
            self._progress = None

    def snapshot(self) -> ScanProgress | None:
        with self._lock:
            return self._progress


# One per process, like scan_lock: the manual scan route and the scheduler both report here.
scan_progress = ProgressTracker()
