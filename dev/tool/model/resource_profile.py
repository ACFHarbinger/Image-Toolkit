"""Resource, Latency, and Causal Profiling models (Track B Phase 5, issue #397).

Host attachment: shares Track A's flame + memory views — this module
builds *on* the existing ``FlameNode``/``FlameGraph``
(:mod:`tool.model.flame_graph`) and ``TimeSeries``
(:mod:`tool.model.metrics_timeline`) models. It is not a second
profiler: nothing here samples a live process (no py-spy, no coz
binary). Instead it derives planning estimates from *recorded* profiles:

- :class:`CausalImpactCurve`: the coz-style "what if this frame were X%
  faster?" question answered analytically from a recorded flame tree via
  Amdahl's bound. A real coz run measures the curve experimentally
  (virtual speedups via cross-thread delays); this derives the upper
  bound the measurement would converge to, which is the correct
  host-side artifact to chart against Track A flame views.
- :class:`MemoryArena`: a named RAM/VRAM allocation arena tracked as a
  ``TimeSeries`` of allocated bytes, with peak/growth/leak-suspect
  summaries for the memory views.
- :func:`estimate_latency_little_law`: Little's-law queueing estimate
  (L = λW) turning an arrival rate and mean service time into a mean
  in-system latency prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .flame_graph import FlameGraph, FlameNode
from .metrics_timeline import TimeSeries


@dataclass
class VirtualSpeedupPoint:
    """One point on a causal-impact curve: speedup factor -> gain."""

    speedup: float  # 1.0 = +100% faster (half the time); 0.2 = +20%
    predicted_gain: float  # fraction of total time eliminated, [0, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {"speedup": self.speedup, "predicted_gain": round(self.predicted_gain, 6)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VirtualSpeedupPoint":
        return cls(speedup=float(data["speedup"]), predicted_gain=float(data["predicted_gain"]))


@dataclass
class CausalImpactCurve:
    """Predicted throughput gain from speeding up one flame-tree frame.

    ``target_share`` is the fraction of total profiled time attributable
    to the target frame (self + descendants on the critical path).
    Gains follow Amdahl's law: ``gain(s) = 1 - 1 / ((1 - p) + p / (1 + s))``.
    """

    target: str
    target_share: float
    baseline_total_ms: float
    points: List[VirtualSpeedupPoint] = field(default_factory=list)

    def predicted_gain(self, speedup: float) -> float:
        """Amdahl gain for a virtual speedup, computed analytically."""
        if speedup < 0:
            raise ValueError("speedup must be >= 0")
        p = min(max(self.target_share, 0.0), 1.0)
        return 1.0 - ((1.0 - p) + p / (1.0 + speedup))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "target_share": self.target_share,
            "baseline_total_ms": self.baseline_total_ms,
            "points": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CausalImpactCurve":
        return cls(
            target=data["target"],
            target_share=float(data.get("target_share", 0.0)),
            baseline_total_ms=float(data.get("baseline_total_ms", 0.0)),
            points=[VirtualSpeedupPoint.from_dict(p) for p in data.get("points", [])],
        )


@dataclass
class ArenaSample:
    """One allocation sample in a memory arena."""

    t_ms: float
    allocated_bytes: int
    reserved_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t_ms": self.t_ms,
            "allocated_bytes": self.allocated_bytes,
            "reserved_bytes": self.reserved_bytes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArenaSample":
        return cls(
            t_ms=float(data["t_ms"]),
            allocated_bytes=int(data["allocated_bytes"]),
            reserved_bytes=int(data.get("reserved_bytes", 0)),
        )


@dataclass
class MemoryArena:
    """A named RAM or VRAM allocation arena with leak/growth summaries.

    The raw samples double as a Track A ``TimeSeries`` (allocated MB over
    time) via :meth:`as_timeseries`, so the memory views render arenas
    without a second data path.
    """

    name: str
    kind: str = "ram"  # "ram" | "vram"
    capacity_bytes: int = 0
    samples: List[ArenaSample] = field(default_factory=list)

    def add_sample(self, t_ms: float, allocated_bytes: int, reserved_bytes: int = 0) -> None:
        self.samples.append(ArenaSample(t_ms, allocated_bytes, reserved_bytes))

    @property
    def peak_bytes(self) -> int:
        return max((s.allocated_bytes for s in self.samples), default=0)

    @property
    def final_bytes(self) -> int:
        return self.samples[-1].allocated_bytes if self.samples else 0

    def growth_bytes(self) -> int:
        """Net growth from first to last sample (leak indicator)."""
        if len(self.samples) < 2:
            return 0
        return self.samples[-1].allocated_bytes - self.samples[0].allocated_bytes

    def over_capacity(self) -> bool:
        return bool(self.capacity_bytes) and self.peak_bytes > self.capacity_bytes

    def as_timeseries(self) -> TimeSeries:
        """Expose allocated-MB history as a Track A TimeSeries."""
        series = TimeSeries(name=f"arena:{self.name}", unit="MB")
        for s in self.samples:
            series.add_point(s.t_ms, s.allocated_bytes / (1024 * 1024), kind=self.kind)
        return series

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "capacity_bytes": self.capacity_bytes,
            "samples": [s.to_dict() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryArena":
        return cls(
            name=data["name"],
            kind=data.get("kind", "ram"),
            capacity_bytes=int(data.get("capacity_bytes", 0)),
            samples=[ArenaSample.from_dict(s) for s in data.get("samples", [])],
        )


def estimate_latency_little_law(arrival_per_sec: float, mean_service_ms: float) -> Dict[str, float]:
    """Little's-law estimate: mean items in system and mean latency.

    L = λW applied to a single-server queue approximation: with arrival
    rate λ (items/sec) and mean service time W, predicts mean queue wait
    plus service time. Returns utilization rho, mean in-system count L,
    and mean latency ms. Raises on non-positive inputs or rho >= 1
    (unstable queue — latency unbounded, which is itself the finding).
    """
    if arrival_per_sec <= 0 or mean_service_ms <= 0:
        raise ValueError("arrival rate and service time must be positive")
    rho = arrival_per_sec * mean_service_ms / 1000.0
    if rho >= 1.0:
        raise ValueError(f"unstable queue: utilization {rho:.3f} >= 1")
    wait_ms = mean_service_ms * rho / (1.0 - rho)
    latency_ms = wait_ms + mean_service_ms
    return {
        "utilization": rho,
        "mean_in_system": arrival_per_sec * latency_ms / 1000.0,
        "mean_latency_ms": latency_ms,
    }


def flame_self_share(node: FlameNode, total_ms: float) -> float:
    """Fraction of total profiled time a flame node accounts for (subtree)."""
    if total_ms <= 0:
        return 0.0
    return node.value / total_ms


def rank_bottlenecks(flame: FlameGraph, top_n: int = 10) -> List[Dict[str, Any]]:
    """Top-down bottleneck attribution: frames ranked by subtree share.

    Orders nodes by inclusive time (value/total) so the icicle view can
    attribute each level's cost to its widest child — the standard
    top-down walk, computed from the recorded tree, no re-profiling.
    """
    ranked: List[Dict[str, Any]] = []
    total = flame.total_time_ms

    def _walk(node: FlameNode, depth: int) -> None:
        ranked.append(
            {
                "name": node.name,
                "depth": depth,
                "share": flame_self_share(node, total),
                "self_time_ms": node.self_time_ms,
                "call_count": node.call_count,
            }
        )
        for child in node.children:
            _walk(child, depth + 1)

    _walk(flame.root, 0)
    ranked.sort(key=lambda r: r["share"], reverse=True)
    return ranked[: max(top_n, 0)]


__all__ = [
    "ArenaSample",
    "CausalImpactCurve",
    "MemoryArena",
    "VirtualSpeedupPoint",
    "estimate_latency_little_law",
    "flame_self_share",
    "rank_bottlenecks",
]
