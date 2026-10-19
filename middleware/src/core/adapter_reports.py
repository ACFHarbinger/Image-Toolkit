"""Adapter-geometry report types (#743/#748) — pure, torch-free.

These dataclasses are the GUI's import surface: the torch compute lives in
``middleware/src/models/hooks/adapter_geometry.py`` and
``middleware/src/models/hooks/loss_slice.py`` (mocked away in GUI tests), so
GUI workers validate ``isinstance`` against these real types and degrade
to "no data" instead of passing fakes into charts or the report card.

Effective rank uses the same 0.99-energy singular-value definition as
``training_hooks.lora_effective_rank``; it is invariant to LoRA alpha
scaling (singular-value ratios are normalized), so file-based reports
need no config.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from middleware.src.core.training_report import RankUtilization

RANK_ENERGY_THRESHOLD = 0.99
SLICE_LABEL = "1-D slice along the leading ΔW direction (not the loss landscape)"


@dataclass(frozen=True)
class ModuleRankRow:
    module: str  # normalized layer key (peft/kohya prefixes stripped)
    effective: int
    rank: int
    max_sv: float
    fro: float

    @property
    def utilization(self) -> float:
        return self.effective / self.rank if self.rank else 0.0


@dataclass(frozen=True)
class CheckpointRankSnapshot:
    label: str  # "epoch 0003" | "final"
    source: str  # adapter file path
    rows: tuple[ModuleRankRow, ...]

    def median_effective(self) -> int:
        values = sorted(r.effective for r in self.rows)
        if not values:
            return 0
        mid = len(values) // 2
        return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) // 2

    @property
    def chosen_rank(self) -> int:
        return max((r.rank for r in self.rows), default=0)

    def utilization(self) -> RankUtilization | None:
        """Median effective vs chosen across modules — the report-card
        signal Kimi's #746 verdict expects."""
        if not self.rows or self.chosen_rank <= 0:
            return None
        return RankUtilization(effective=self.median_effective(), chosen=self.chosen_rank)

    def utilization_at(self, fraction: float) -> float:
        """Share of modules whose effective rank sits at or below
        `fraction` of their chosen rank (rank/4 → 'saturated low')."""
        if not self.rows:
            return 0.0
        hits = sum(1 for r in self.rows if r.effective <= max(1, int(r.rank * fraction)))
        return hits / len(self.rows)

    @property
    def pinned_fraction(self) -> float:
        """Modules whose effective rank equals the chosen rank — the
        'rank is the bottleneck' signal when loss is still falling."""
        if not self.rows:
            return 0.0
        return sum(1 for r in self.rows if r.effective >= r.rank) / len(self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "source": self.source,
            "rows": [asdict(r) for r in self.rows],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointRankSnapshot:
        rows = tuple(ModuleRankRow(**r) for r in data.get("rows", ()))
        return cls(label=str(data.get("label", "")), source=str(data.get("source", "")), rows=rows)


@dataclass(frozen=True)
class RankHistoryReport:
    output_dir: str
    snapshots: tuple[CheckpointRankSnapshot, ...] = ()
    note: str = ""  # why snapshots is empty, or skipped artifacts

    def latest(self) -> CheckpointRankSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "note": self.note,
            "snapshots": [s.to_dict() for s in self.snapshots],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RankHistoryReport:
        return cls(
            output_dir=str(data.get("output_dir", "")),
            note=str(data.get("note", "")),
            snapshots=tuple(CheckpointRankSnapshot.from_dict(s) for s in data.get("snapshots", ())),
        )

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_json_file(cls, path: str | Path) -> RankHistoryReport | None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return cls.from_dict(data) if isinstance(data, dict) else None


@dataclass(frozen=True)
class DirectionSpec:
    """Leading singular pair of a checkpoint's largest-‖ΔW‖ module."""

    module: str
    sigma: float
    energy_fraction: float  # σ1² / Σσ² within that module
    chosen_rank: int


@dataclass(frozen=True)
class LossSliceResult:
    checkpoint: str
    module: str
    sigma: float
    energy_fraction: float
    alphas: tuple[float, ...]
    losses: tuple[float, ...]
    eval_images: int
    seed: int
    base_model: str
    num_points: int = 21
    label: str = field(default=SLICE_LABEL, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint": self.checkpoint,
            "module": self.module,
            "sigma": self.sigma,
            "energy_fraction": self.energy_fraction,
            "alphas": list(self.alphas),
            "losses": list(self.losses),
            "eval_images": self.eval_images,
            "seed": self.seed,
            "base_model": self.base_model,
            "num_points": self.num_points,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LossSliceResult:
        return cls(
            checkpoint=str(data.get("checkpoint", "")),
            module=str(data.get("module", "")),
            sigma=float(data.get("sigma", 0.0)),
            energy_fraction=float(data.get("energy_fraction", 0.0)),
            alphas=tuple(float(a) for a in data.get("alphas", ())),
            losses=tuple(float(v) for v in data.get("losses", ())),
            eval_images=int(data.get("eval_images", 0)),
            seed=int(data.get("seed", 0)),
            base_model=str(data.get("base_model", "")),
            num_points=int(data.get("num_points", len(data.get("alphas", ())) or 0)),
        )

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_json_file(cls, path: str | Path) -> LossSliceResult | None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return cls.from_dict(data) if isinstance(data, dict) else None


__all__ = [
    "CheckpointRankSnapshot",
    "DirectionSpec",
    "LossSliceResult",
    "ModuleRankRow",
    "RANK_ENERGY_THRESHOLD",
    "RankHistoryReport",
    "SLICE_LABEL",
]
