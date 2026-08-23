"""Timeseries & 2D Metrics Timeline Models (Issue #416 / D43 / D45).

Provides high-performance timeseries downsampling, memory/RSS lifecycle
progression, and benchmark trend analytics for 2D visual charts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TimePoint:
    """A single timeseries data point."""

    t_ms: float
    val: float
    tag: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t_ms": round(self.t_ms, 2),
            "val": round(self.val, 4),
            "tag": self.tag,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimePoint:
        return cls(
            t_ms=float(data["t_ms"]),
            val=float(data["val"]),
            tag=data.get("tag"),
            meta=dict(data.get("meta", {})),
        )


@dataclass
class TimeSeries:
    """A named timeseries with LTTB downsampling for smooth 60fps chart rendering."""

    name: str
    unit: str  # "MB", "ms", "count", "score", "%"
    points: List[TimePoint] = field(default_factory=list)
    alert_threshold: Optional[float] = None

    def add_point(self, t_ms: float, val: float, tag: Optional[str] = None, **meta: Any) -> None:
        self.points.append(TimePoint(t_ms=t_ms, val=val, tag=tag, meta=meta))

    @property
    def min_val(self) -> float:
        return min((p.val for p in self.points), default=0.0)

    @property
    def max_val(self) -> float:
        return max((p.val for p in self.points), default=0.0)

    @property
    def avg_val(self) -> float:
        if not self.points:
            return 0.0
        return sum(p.val for p in self.points) / len(self.points)

    def downsample(self, target_points: int = 500) -> List[TimePoint]:
        """Downsample points using Largest-Triangle-Three-Buckets (LTTB) algorithm."""
        if len(self.points) <= target_points or target_points < 3:
            return list(self.points)

        # LTTB downsampling
        sampled: List[TimePoint] = [self.points[0]]
        every = (len(self.points) - 2) / (target_points - 2)
        a = 0

        for i in range(target_points - 2):
            # Calculate average point for the next bucket (C)
            avg_x, avg_y = 0.0, 0.0
            avg_range_start = int((i + 1) * every) + 1
            avg_range_end = min(int((i + 2) * every) + 1, len(self.points))
            avg_range_len = max(1, avg_range_end - avg_range_start)

            for j in range(avg_range_start, avg_range_end):
                avg_x += self.points[j].t_ms
                avg_y += self.points[j].val

            avg_x /= avg_range_len
            avg_y /= avg_range_len

            # Find point in current bucket (B) with largest triangle area
            range_offs = int(i * every) + 1
            range_to = int((i + 1) * every) + 1

            point_a = self.points[a]
            max_area = -1.0
            max_idx = range_offs

            for idx in range(range_offs, min(range_to, len(self.points))):
                pt = self.points[idx]
                area = abs(
                    (point_a.t_ms - avg_x) * (pt.val - point_a.val)
                    - (point_a.t_ms - pt.t_ms) * (avg_y - point_a.val)
                ) * 0.5
                if area > max_area:
                    max_area = area
                    max_idx = idx

            sampled.append(self.points[max_idx])
            a = max_idx

        sampled.append(self.points[-1])
        return sampled

    def to_dict(self, downsample_to: Optional[int] = None) -> Dict[str, Any]:
        points = self.downsample(downsample_to) if downsample_to else self.points
        return {
            "name": self.name,
            "unit": self.unit,
            "alert_threshold": self.alert_threshold,
            "min_val": round(self.min_val, 4),
            "max_val": round(self.max_val, 4),
            "avg_val": round(self.avg_val, 4),
            "points": [p.to_dict() for p in points],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimeSeries:
        series = cls(
            name=data["name"],
            unit=data.get("unit", ""),
            alert_threshold=data.get("alert_threshold"),
        )
        series.points = [TimePoint.from_dict(p) for p in data.get("points", [])]
        return series
