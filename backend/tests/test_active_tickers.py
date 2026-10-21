from app.scanning.active import MAX_ACTIVE_TICKERS, select_active_tickers
from tests.scan_fixtures import snapshot


def test_select_active_by_relative_volume_change_or_screen_hit():
    snapshots = [
        snapshot("QUIET", relative_volume=1.0, change=1.0),
        snapshot("VOLUME", relative_volume=1.5, change=0.5),
        snapshot("MOVER", relative_volume=0.8, change=-5.0),
        snapshot("AFTERHOURS", relative_volume=0.8, change=0.0, after_hours_change=6.0),
        snapshot("HIT", relative_volume=0.5, change=0.0),
        snapshot("NODATA", relative_volume=None, change=None, after_hours_change=None),
    ]

    active = select_active_tickers(snapshots, screen_hits={"HIT"})

    assert set(active) == {"VOLUME", "MOVER", "AFTERHOURS", "HIT"}
    assert active[0] == "HIT"  # screen hits first


def test_select_active_caps_at_forty_most_active_first():
    snapshots = [snapshot(f"T{index:02d}", relative_volume=2.0 + index) for index in range(50)]

    active = select_active_tickers(snapshots, screen_hits=set())

    assert len(active) == MAX_ACTIVE_TICKERS == 40
    assert active[0] == "T49"
    assert "T00" not in active
