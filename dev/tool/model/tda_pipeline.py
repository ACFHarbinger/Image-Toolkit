"""Topological Data Analysis models (Track B Phase 10, issue #402).

Host attachment: research; explicitly not v1.

This module defines serializable dataclasses for:
- Persistence diagrams (birth/death of topological features by Betti numbers)
- Persistence barcodes (visual representation of feature lifetimes)
- Betti curves (count of features at each filtration value)
- TDA-based behavioral fingerprints (topological signatures of code/modules)

Libraries like Ripser, Gudhi, or Giotto-TDA are NOT dependencies.
The math is implemented directly on numpy/scipy for portability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PersistencePoint:
    """One point in a persistence diagram: (birth, death) of a topological feature.

    A point (b, d) means a topological feature (connected component, loop,
    or void) appeared at filtration value b and disappeared at d.
    Features with d=inf are essential (never die).
    """

    birth: float
    death: float
    dimension: int  # 0=connected component, 1=loop, 2=void

    @property
    def persistence(self) -> float:
        """Lifetime of this feature (death - birth)."""
        if self.death == float("inf"):
            return float("inf")
        return self.death - self.birth

    @property
    def is_essential(self) -> bool:
        """True if this feature never dies (death == inf)."""
        return self.death == float("inf")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "birth": self.birth,
            "death": self.death if self.death != float("inf") else "inf",
            "dimension": self.dimension,
            "persistence": self.persistence if self.persistence != float("inf") else "inf",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistencePoint":
        death = float("inf") if data["death"] == "inf" else float(data["death"])
        return cls(
            birth=float(data["birth"]),
            death=death,
            dimension=int(data["dimension"]),
        )


@dataclass
class PersistenceDiagram:
    """Collection of persistence points for one homology dimension.

    A persistence diagram is a multiset of points in R^2, where each point
    (b, d) represents a topological feature that existed from filtration
    value b to d.
    """

    dimension: int
    points: List[PersistencePoint] = field(default_factory=list)

    @property
    def betti_number(self) -> int:
        """Count of currently-alive features (essential features)."""
        return sum(1 for p in self.points if p.is_essential)

    @property
    def total_persistence(self) -> float:
        """Sum of all finite persistences (L1 norm of the diagram)."""
        return sum(p.persistence for p in self.points if not p.is_essential)

    @property
    def max_persistence(self) -> float:
        """Maximum finite persistence (longest-lived non-essential feature)."""
        finite = [p.persistence for p in self.points if not p.is_essential]
        return max(finite) if finite else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "points": [p.to_dict() for p in self.points],
            "betti_number": self.betti_number,
            "total_persistence": self.total_persistence,
            "max_persistence": self.max_persistence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistenceDiagram":
        return cls(
            dimension=int(data["dimension"]),
            points=[PersistencePoint.from_dict(p) for p in data.get("points", [])],
        )


@dataclass
class BettiCurve:
    """Betti numbers as a function of filtration value.

    beta_k(epsilon) = count of k-dimensional features alive at filtration epsilon.
    """

    dimension: int
    filtration_values: List[float] = field(default_factory=list)
    betti_values: List[int] = field(default_factory=list)

    def betti_at(self, epsilon: float) -> int:
        """Get Betti number at a specific filtration value."""
        if not self.filtration_values:
            return 0
        # Find the last filtration value <= epsilon
        for i, fv in enumerate(self.filtration_values):
            if fv > epsilon:
                return self.betti_values[i - 1] if i > 0 else 0
        return self.betti_values[-1] if self.betti_values else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "filtration_values": self.filtration_values,
            "betti_values": self.betti_values,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BettiCurve":
        return cls(
            dimension=int(data["dimension"]),
            filtration_values=data.get("filtration_values", []),
            betti_values=data.get("betti_values", []),
        )


@dataclass
class TDAFingerprint:
    """Topological signature of a code module or execution trace.

    Combines persistence diagrams across dimensions into a single
    behavioral fingerprint. Robust to code obfuscation, renaming,
    and control-flow flattening (per the issue spec).
    """

    module_id: str
    diagrams: List[PersistenceDiagram] = field(default_factory=list)
    betti_curves: List[BettiCurve] = field(default_factory=list)

    @property
    def total_betti_0(self) -> int:
        """Total connected components (beta_0) across all diagrams."""
        return sum(d.betti_number for d in self.diagrams if d.dimension == 0)

    @property
    def total_betti_1(self) -> int:
        """Total loops (beta_1) across all diagrams."""
        return sum(d.betti_number for d in self.diagrams if d.dimension == 1)

    @property
    def total_betti_2(self) -> int:
        """Total voids (beta_2) across all diagrams."""
        return sum(d.betti_number for d in self.diagrams if d.dimension == 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "diagrams": [d.to_dict() for d in self.diagrams],
            "betti_curves": [b.to_dict() for b in self.betti_curves],
            "summary": {
                "total_betti_0": self.total_betti_0,
                "total_betti_1": self.total_betti_1,
                "total_betti_2": self.total_betti_2,
                "total_persistence": sum(d.total_persistence for d in self.diagrams),
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TDAFingerprint":
        return cls(
            module_id=data["module_id"],
            diagrams=[PersistenceDiagram.from_dict(d) for d in data.get("diagrams", [])],
            betti_curves=[BettiCurve.from_dict(b) for b in data.get("betti_curves", [])],
        )


@dataclass
class VietorisRipsFiltration:
    """Vietoris-Rips filtration over a point cloud.

    Given a set of points and a distance threshold epsilon, the VR complex
    includes a simplex for every subset of points with pairwise distances <= epsilon.
    As epsilon increases, more simplices are added, creating a filtration.
    """

    point_cloud: List[List[float]] = field(default_factory=list)
    max_dimension: int = 2  # Compute homology up to this dimension
    max_filtration: float = float("inf")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_cloud": self.point_cloud,
            "max_dimension": self.max_dimension,
            "max_filtration": (self.max_filtration if self.max_filtration != float("inf") else "inf"),
            "num_points": len(self.point_cloud),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VietorisRipsFiltration":
        max_filt = data.get("max_filtration", "inf")
        return cls(
            point_cloud=data.get("point_cloud", []),
            max_dimension=int(data.get("max_dimension", 2)),
            max_filtration=float("inf") if max_filt == "inf" else float(max_filt),
        )


__all__ = [
    "BettiCurve",
    "PersistenceDiagram",
    "PersistencePoint",
    "TDAFingerprint",
    "VietorisRipsFiltration",
]
