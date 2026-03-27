"""Tests for the market-research trend monitor."""

import pytest
from datetime import datetime, timezone, date

from dbc_inventory.market_research.trend_monitor import TrendMonitor, TrendResult, VolumeSnapshot


class TestVolumeSnapshot:
    def test_creates_with_defaults(self):
        snap = VolumeSnapshot(keyword="rosary beads", volume=45_000)
        assert snap.keyword == "rosary beads"
        assert snap.volume == 45_000
        assert snap.recorded_at is not None

    def test_negative_volume_raises(self):
        with pytest.raises(ValueError, match="volume must be"):
            VolumeSnapshot(keyword="rosary beads", volume=-1)


class TestTrendResult:
    def _make_snapshots(self, keyword: str, volumes: list[int]) -> list[VolumeSnapshot]:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        from datetime import timedelta

        return [
            VolumeSnapshot(keyword=keyword, volume=v, recorded_at=base + timedelta(weeks=i))
            for i, v in enumerate(volumes)
        ]

    def test_average_volume(self):
        snaps = self._make_snapshots("rosary beads", [100, 200, 300])
        result = TrendResult(keyword="rosary beads", snapshots=snaps)
        assert result.average_volume == 200.0

    def test_momentum_positive(self):
        snaps = self._make_snapshots("rosary beads", [100, 150])
        result = TrendResult(keyword="rosary beads", snapshots=snaps)
        assert result.momentum == 50.0

    def test_momentum_negative(self):
        snaps = self._make_snapshots("rosary beads", [200, 100])
        result = TrendResult(keyword="rosary beads", snapshots=snaps)
        assert result.momentum == -50.0

    def test_momentum_zero_when_single_snapshot(self):
        snaps = self._make_snapshots("rosary beads", [100])
        result = TrendResult(keyword="rosary beads", snapshots=snaps)
        assert result.momentum == 0.0

    def test_momentum_zero_when_first_volume_zero(self):
        snaps = self._make_snapshots("rosary beads", [0, 100])
        result = TrendResult(keyword="rosary beads", snapshots=snaps)
        assert result.momentum == 0.0

    def test_is_trending_up(self):
        snaps = self._make_snapshots("rosary", [100, 110])
        result = TrendResult(keyword="rosary", snapshots=snaps)
        assert result.is_trending_up is True

    def test_is_not_trending_up(self):
        snaps = self._make_snapshots("rosary", [110, 100])
        result = TrendResult(keyword="rosary", snapshots=snaps)
        assert result.is_trending_up is False

    def test_peak_volume(self):
        snaps = self._make_snapshots("rosary", [100, 300, 200])
        result = TrendResult(keyword="rosary", snapshots=snaps)
        assert result.peak_volume == 300

    def test_empty_snapshots(self):
        result = TrendResult(keyword="rosary", snapshots=[])
        assert result.average_volume == 0.0
        assert result.momentum == 0.0
        assert result.peak_volume == 0


class TestTrendMonitor:
    def setup_method(self):
        self.monitor = TrendMonitor()

    def test_record_returns_snapshot(self):
        snap = self.monitor.record("rosary beads", 45_000)
        assert isinstance(snap, VolumeSnapshot)
        assert snap.keyword == "rosary beads"

    def test_get_trend_returns_none_for_unknown(self):
        assert self.monitor.get_trend("unknown keyword") is None

    def test_get_trend_after_recording(self):
        self.monitor.record("rosary beads", 45_000)
        result = self.monitor.get_trend("rosary beads")
        assert result is not None
        assert result.keyword == "rosary beads"
        assert len(result.snapshots) == 1

    def test_multiple_records_accumulate(self):
        self.monitor.record("rosary beads", 45_000)
        self.monitor.record("rosary beads", 47_500)
        result = self.monitor.get_trend("rosary beads")
        assert len(result.snapshots) == 2

    def test_snapshots_sorted_chronologically(self):
        from datetime import timedelta

        t1 = datetime(2026, 2, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, tzinfo=timezone.utc)  # older
        self.monitor.record("rosary beads", 50_000, recorded_at=t1)
        self.monitor.record("rosary beads", 45_000, recorded_at=t2)
        result = self.monitor.get_trend("rosary beads")
        assert result.snapshots[0].recorded_at < result.snapshots[1].recorded_at

    def test_record_batch(self):
        ts = datetime(2026, 1, 15, tzinfo=timezone.utc)
        snaps = self.monitor.record_batch(
            [("rosary beads", 45_000), ("prayer beads", 18_000)],
            recorded_at=ts,
        )
        assert len(snaps) == 2
        assert self.monitor.get_trend("rosary beads") is not None
        assert self.monitor.get_trend("prayer beads") is not None

    def test_get_trends_min_snapshots_filter(self):
        self.monitor.record("rosary beads", 45_000)
        self.monitor.record("prayer beads", 18_000)
        self.monitor.record("prayer beads", 20_000)
        results = self.monitor.get_trends(min_snapshots=2)
        keywords = [r.keyword for r in results]
        assert "prayer beads" in keywords
        assert "rosary beads" not in keywords

    def test_top_trending_returns_positive_momentum_only(self):
        from datetime import timedelta

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.monitor.record("rising", 100, recorded_at=base)
        self.monitor.record("rising", 200, recorded_at=base + timedelta(weeks=1))
        self.monitor.record("falling", 200, recorded_at=base)
        self.monitor.record("falling", 100, recorded_at=base + timedelta(weeks=1))

        top = self.monitor.top_trending()
        keywords = [r.keyword for r in top]
        assert "rising" in keywords
        assert "falling" not in keywords

    def test_top_trending_sorted_by_momentum_desc(self):
        from datetime import timedelta

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for kw, v1, v2 in [("a", 100, 200), ("b", 100, 150), ("c", 100, 300)]:
            self.monitor.record(kw, v1, recorded_at=base)
            self.monitor.record(kw, v2, recorded_at=base + timedelta(weeks=1))

        top = self.monitor.top_trending()
        momenta = [r.momentum for r in top]
        assert momenta == sorted(momenta, reverse=True)

    def test_top_declining(self):
        from datetime import timedelta

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.monitor.record("falling", 200, recorded_at=base)
        self.monitor.record("falling", 100, recorded_at=base + timedelta(weeks=1))

        declining = self.monitor.top_declining()
        assert any(r.keyword == "falling" for r in declining)

    def test_top_trending_as_of_filter(self):
        from datetime import timedelta

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Record two snapshots in Jan then one in March
        self.monitor.record("kw", 100, recorded_at=base)
        self.monitor.record("kw", 50, recorded_at=base + timedelta(weeks=2))  # drops
        self.monitor.record("kw", 200, recorded_at=base + timedelta(weeks=10))  # rises

        # As of end of January the trend is falling
        top = self.monitor.top_trending(as_of=date(2026, 1, 31))
        assert not any(r.keyword == "kw" for r in top)

    def test_keywords(self):
        self.monitor.record("rosary beads", 45_000)
        self.monitor.record("prayer beads", 18_000)
        assert set(self.monitor.keywords()) == {"rosary beads", "prayer beads"}

    def test_clear(self):
        self.monitor.record("rosary beads", 45_000)
        self.monitor.clear()
        assert self.monitor.keywords() == []
