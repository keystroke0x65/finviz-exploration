from datetime import datetime, timezone

from app.scanning.progress import ProgressTracker, ScanProgress

STARTED = datetime(2026, 11, 16, 14, 41, tzinfo=timezone.utc)


def test_tracker_reports_nothing_when_idle():
    assert ProgressTracker().snapshot() is None


def test_tracker_tracks_phase_total_and_current_ticker():
    tracker = ProgressTracker()
    tracker.start("automatic", STARTED)
    assert tracker.snapshot() == ScanProgress("automatic", "preparing", 0, 0, None, STARTED)

    tracker.set_total(3)
    tracker.set_phase("scanning")
    tracker.begin_ticker("BBB", 1)

    assert tracker.snapshot() == ScanProgress("automatic", "scanning", 1, 3, "BBB", STARTED)


def test_finishing_counts_every_stock_as_done():
    tracker = ProgressTracker()
    tracker.start("manual", STARTED)
    tracker.set_total(3)
    tracker.begin_ticker("CCC", 2)

    tracker.set_phase("finishing")

    assert tracker.snapshot() == ScanProgress("manual", "finishing", 3, 3, None, STARTED)


def test_finish_clears_progress():
    tracker = ProgressTracker()
    tracker.start("manual", STARTED)

    tracker.finish()

    assert tracker.snapshot() is None


def test_updates_without_a_running_scan_are_ignored():
    tracker = ProgressTracker()

    tracker.set_phase("scanning")
    tracker.begin_ticker("AAA", 0)

    assert tracker.snapshot() is None
