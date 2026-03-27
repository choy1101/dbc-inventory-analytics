"""Market-research trend monitor for the Rosary / handmade-craft niche (2026).

Tracks keyword-level trends by storing historical search-volume snapshots
and computing momentum scores so DivineBeadCraft can spot rising demand
before competitors.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VolumeSnapshot:
    """A single search-volume observation for one keyword."""

    keyword: str
    volume: int
    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )

    def __post_init__(self) -> None:
        if self.volume < 0:
            raise ValueError(f"volume must be ≥ 0, got {self.volume}")


@dataclass
class TrendResult:
    """Trend analysis for a single keyword over a series of snapshots."""

    keyword: str
    snapshots: list[VolumeSnapshot]

    @property
    def volumes(self) -> list[int]:
        return [s.volume for s in self.snapshots]

    @property
    def average_volume(self) -> float:
        if not self.snapshots:
            return 0.0
        return statistics.mean(self.volumes)

    @property
    def momentum(self) -> float:
        """Percentage change from the first snapshot to the last.

        Returns 0.0 when there are fewer than two snapshots or the first
        snapshot has a zero volume.
        """
        if len(self.snapshots) < 2 or self.snapshots[0].volume == 0:
            return 0.0
        first = self.snapshots[0].volume
        last = self.snapshots[-1].volume
        return round((last - first) / first * 100, 2)

    @property
    def is_trending_up(self) -> bool:
        """True when momentum is positive."""
        return self.momentum > 0

    @property
    def peak_volume(self) -> int:
        if not self.snapshots:
            return 0
        return max(self.volumes)

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"{self.keyword!r:40s}  avg={self.average_volume:.0f}"
            f"  momentum={self.momentum:+.1f}%"
            f"  {'↑ trending' if self.is_trending_up else '↓ declining'}"
        )


# ---------------------------------------------------------------------------
# Trend monitor
# ---------------------------------------------------------------------------


class TrendMonitor:
    """Collects search-volume snapshots and surfaces trending keywords.

    Usage example::

        monitor = TrendMonitor()
        monitor.record("rosary beads", 45_000)
        monitor.record("rosary beads", 47_500)  # next week
        report = monitor.get_trends()
        for result in report:
            print(result)
    """

    def __init__(self) -> None:
        self._data: dict[str, list[VolumeSnapshot]] = {}

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def record(
        self,
        keyword: str,
        volume: int,
        *,
        recorded_at: datetime | None = None,
    ) -> VolumeSnapshot:
        """Record a search-volume observation for *keyword*.

        Parameters
        ----------
        keyword:
            The search keyword / phrase being tracked.
        volume:
            Estimated monthly search volume at the time of recording.
        recorded_at:
            Timestamp for this observation.  Defaults to *now* (UTC).

        Returns
        -------
        VolumeSnapshot
            The snapshot that was stored.
        """
        snapshot = VolumeSnapshot(
            keyword=keyword,
            volume=volume,
            recorded_at=recorded_at or datetime.now(tz=timezone.utc),
        )
        self._data.setdefault(keyword, []).append(snapshot)
        # Keep snapshots ordered chronologically.
        self._data[keyword].sort(key=lambda s: s.recorded_at)
        return snapshot

    def record_batch(
        self,
        observations: Sequence[tuple[str, int]],
        *,
        recorded_at: datetime | None = None,
    ) -> list[VolumeSnapshot]:
        """Record multiple observations at the same timestamp.

        Parameters
        ----------
        observations:
            An iterable of ``(keyword, volume)`` pairs.
        recorded_at:
            Shared timestamp for all observations in this batch.
        """
        ts = recorded_at or datetime.now(tz=timezone.utc)
        return [self.record(kw, vol, recorded_at=ts) for kw, vol in observations]

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_trend(self, keyword: str) -> TrendResult | None:
        """Return trend data for a single keyword, or *None* if not tracked."""
        snapshots = self._data.get(keyword)
        if snapshots is None:
            return None
        return TrendResult(keyword=keyword, snapshots=list(snapshots))

    def get_trends(self, *, min_snapshots: int = 1) -> list[TrendResult]:
        """Return trend results for all tracked keywords.

        Parameters
        ----------
        min_snapshots:
            Only include keywords that have at least this many snapshots.
        """
        results = [
            TrendResult(keyword=kw, snapshots=list(snaps))
            for kw, snaps in self._data.items()
            if len(snaps) >= min_snapshots
        ]
        return results

    def top_trending(
        self,
        *,
        n: int = 10,
        min_snapshots: int = 2,
        as_of: date | None = None,
    ) -> list[TrendResult]:
        """Return the *n* keywords with the highest positive momentum.

        Parameters
        ----------
        n:
            Maximum number of results to return.
        min_snapshots:
            Minimum snapshot count required to include a keyword.
        as_of:
            If supplied, only snapshots recorded on or before this date are
            considered.  Useful for back-testing.
        """
        results = self.get_trends(min_snapshots=min_snapshots)

        if as_of is not None:
            cutoff = datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59, tzinfo=timezone.utc)
            filtered: list[TrendResult] = []
            for r in results:
                snaps = [s for s in r.snapshots if s.recorded_at <= cutoff]
                if len(snaps) >= min_snapshots:
                    filtered.append(TrendResult(keyword=r.keyword, snapshots=snaps))
            results = filtered

        trending = [r for r in results if r.is_trending_up]
        return sorted(trending, key=lambda r: r.momentum, reverse=True)[:n]

    def top_declining(self, *, n: int = 10, min_snapshots: int = 2) -> list[TrendResult]:
        """Return the *n* keywords with the steepest negative momentum."""
        results = self.get_trends(min_snapshots=min_snapshots)
        declining = [r for r in results if not r.is_trending_up and r.momentum != 0]
        return sorted(declining, key=lambda r: r.momentum)[:n]

    def keywords(self) -> list[str]:
        """Return all tracked keyword strings."""
        return list(self._data.keys())

    def clear(self) -> None:
        """Remove all recorded data."""
        self._data.clear()
