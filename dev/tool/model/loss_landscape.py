"""ML model & loss-landscape models (Track B Phase 2, issue #394).

Host attachment: future plugin, scoped to the live models (AnimeStitchNet,
BiRefNet, LoFTR, DINOv2); issue #371 retired the RLHF/DRL scope and it is
not resurrected here. These are the *data* half of the visualizer — plain
serializable dataclasses the host's web/3D views can chart directly. The
computations live in :mod:`tool.research.loss_landscape`; nothing in this
module imports torch or the model wrappers, so the host can load surfaces,
spectra, trajectories, and activation atlases without the GPU stack.

- :class:`LossSurface`: filter-normalized (Li et al., 2018) 2D slice of the
  loss function around trained weights, plus the optimizer trajectory
  across that slice.
- :class:`HessianSpectrum`: Hutchinson trace estimate + Stochastic Lanczos
  Quadrature eigenvalue density — the local sharpness/flatness geometry.
- :class:`WeightTrajectory`: per-epoch weight/gradient norms and their
  PCA / t-SNE projection, showing how training moves through weight space.
- :class:`ActivationAtlas` / :class:`AttentionMap`: hook-captured layer
  activations reduced to a 2D embedding, and downsampled attention maps
  for the transformer backbones (LoFTR / DINOv2 / BiRefNet-Swin).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TrajectoryPoint:
    """One optimizer step plotted on a loss surface slice."""

    step: int
    alpha: float
    beta: float
    loss: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "alpha": round(self.alpha, 6),
            "beta": round(self.beta, 6),
            "loss": round(self.loss, 6),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrajectoryPoint":
        return cls(
            step=int(data["step"]),
            alpha=float(data["alpha"]),
            beta=float(data["beta"]),
            loss=float(data["loss"]),
        )


@dataclass
class LossSurface:
    """A 2D slice of the loss function around trained weights.

    Directions ``dir_x`` / ``dir_y`` are filter-normalized random Gaussian
    directions (same shape as the model parameters); the slice evaluates
    ``loss(theta + alpha * dir_x + beta * dir_y)`` over a rectangular grid.
    ``losses`` is row-major: ``losses[row][col]`` = loss at
    ``beta = beta_range[row]``, ``alpha = alpha_range[col]``.
    ``trajectory`` is the optimizer's actual path projected onto the same
    two directions — the "where training actually went" overlay.
    """

    model_name: str
    alpha_range: List[float]
    beta_range: List[float]
    losses: List[List[float]]
    dir_x_norm: float = 0.0
    dir_y_norm: float = 0.0
    baseline_loss: float = 0.0
    trajectory: List[TrajectoryPoint] = field(default_factory=list)

    @property
    def resolution(self) -> Tuple[int, int]:
        """(rows, cols) of the sampled grid."""
        return (len(self.losses), len(self.losses[0]) if self.losses else 0)

    def min_loss(self) -> float:
        flat = [v for row in self.losses for v in row]
        return min(flat) if flat else 0.0

    def max_loss(self) -> float:
        flat = [v for row in self.losses for v in row]
        return max(flat) if flat else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "alpha_range": self.alpha_range,
            "beta_range": self.beta_range,
            "losses": self.losses,
            "dir_x_norm": round(self.dir_x_norm, 6),
            "dir_y_norm": round(self.dir_y_norm, 6),
            "baseline_loss": round(self.baseline_loss, 6),
            "trajectory": [p.to_dict() for p in self.trajectory],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LossSurface":
        return cls(
            model_name=data["model_name"],
            alpha_range=[float(a) for a in data["alpha_range"]],
            beta_range=[float(b) for b in data["beta_range"]],
            losses=[[float(v) for v in row] for row in data["losses"]],
            dir_x_norm=float(data.get("dir_x_norm", 0.0)),
            dir_y_norm=float(data.get("dir_y_norm", 0.0)),
            baseline_loss=float(data.get("baseline_loss", 0.0)),
            trajectory=[TrajectoryPoint.from_dict(p) for p in data.get("trajectory", [])],
        )


@dataclass
class EigenDensityBin:
    """One bin of the Hessian eigenvalue spectral density (ESD)."""

    center: float
    weight: float  # estimated density mass in this bin

    def to_dict(self) -> Dict[str, Any]:
        return {"center": round(self.center, 6), "weight": round(self.weight, 6)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EigenDensityBin":
        return cls(center=float(data["center"]), weight=float(data["weight"]))


@dataclass
class HessianSpectrum:
    """Local loss-landscape geometry at trained weights.

    ``trace_estimate`` is the Hutchinson estimate of ``Tr(H)`` (average
    local curvature); ``density`` is the SLQ eigenvalue spectral density —
    a sharp right edge (large positive eigenvalues) marks a sharp minimum,
    a soft/negative-heavy density marks a flat or saddle region.
    """

    model_name: str
    trace_estimate: float = 0.0
    num_probes: int = 0
    lanczos_steps: int = 0
    density: List[EigenDensityBin] = field(default_factory=list)

    @property
    def min_eigenvalue(self) -> float:
        return min((b.center for b in self.density), default=0.0)

    @property
    def max_eigenvalue(self) -> float:
        return max((b.center for b in self.density), default=0.0)

    def sharpness(self) -> float:
        """Right-edge magnitude — the PyHessian-style sharpness summary."""
        return max(self.max_eigenvalue, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "trace_estimate": round(self.trace_estimate, 6),
            "num_probes": self.num_probes,
            "lanczos_steps": self.lanczos_steps,
            "min_eigenvalue": round(self.min_eigenvalue, 6),
            "max_eigenvalue": round(self.max_eigenvalue, 6),
            "sharpness": round(self.sharpness(), 6),
            "density": [b.to_dict() for b in self.density],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HessianSpectrum":
        return cls(
            model_name=data["model_name"],
            trace_estimate=float(data.get("trace_estimate", 0.0)),
            num_probes=int(data.get("num_probes", 0)),
            lanczos_steps=int(data.get("lanczos_steps", 0)),
            density=[EigenDensityBin.from_dict(b) for b in data.get("density", [])],
        )


@dataclass
class TrajectoryProjection:
    """Per-epoch weight/gradient trajectory projected to 2D/3D.

    ``method`` is ``"pca"`` or ``"tsne"``. ``points[i]`` corresponds to
    epoch/step ``steps[i]``; ``norms_weight`` / ``norms_grad`` keep the raw
    distance-from-init and gradient magnitudes so the host can color or
    size points by them even when the embedding is nonlinear (t-SNE).
    """

    model_name: str
    method: str = "pca"
    steps: List[int] = field(default_factory=list)
    points: List[List[float]] = field(default_factory=list)  # [[x, y] or [x, y, z]]
    explained_variance: List[float] = field(default_factory=list)
    norms_weight: List[float] = field(default_factory=list)
    norms_grad: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "method": self.method,
            "steps": self.steps,
            "points": [list(p) for p in self.points],
            "explained_variance": [round(v, 6) for v in self.explained_variance],
            "norms_weight": [round(v, 6) for v in self.norms_weight],
            "norms_grad": [round(v, 6) for v in self.norms_grad],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrajectoryProjection":
        return cls(
            model_name=data["model_name"],
            method=data.get("method", "pca"),
            steps=[int(s) for s in data.get("steps", [])],
            points=[list(p) for p in data.get("points", [])],
            explained_variance=[float(v) for v in data.get("explained_variance", [])],
            norms_weight=[float(v) for v in data.get("norms_weight", [])],
            norms_grad=[float(v) for v in data.get("norms_grad", [])],
        )


@dataclass
class AttentionMap:
    """One downsampled attention map from a transformer backbone.

    ``grid`` is a small square 2D list (e.g. 14x14 tokens, pooled from the
    native resolution) of mean attention mass per position — enough for a
    heatmap overlay without shipping the full ``heads × tokens × tokens``
    tensor through the host.
    """

    layer_name: str
    head: int = -1  # -1 = all heads averaged
    grid: List[List[float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_name": self.layer_name,
            "head": self.head,
            "grid": [[round(v, 6) for v in row] for row in self.grid],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttentionMap":
        return cls(
            layer_name=data["layer_name"],
            head=int(data.get("head", -1)),
            grid=[[float(v) for v in row] for row in data.get("grid", [])],
        )


@dataclass
class ActivationAtlas:
    """Layer activations reduced to a 2D embedding (the "atlas" view).

    ``embedding[i]`` is the 2D coordinate of activation sample ``i``;
    ``channel_means[i]`` the per-channel mean of that sample (so the host
    can reconstruct a representative tile image later). ``spatial_shape``
    records the native activation shape before flattening. ``attention``
    holds any attention maps captured from the same layer pass.
    """

    model_name: str
    layer_name: str
    spatial_shape: List[int] = field(default_factory=list)
    embedding: List[List[float]] = field(default_factory=list)
    channel_means: List[List[float]] = field(default_factory=list)
    sample_ids: List[str] = field(default_factory=list)
    attention: List[AttentionMap] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "layer_name": self.layer_name,
            "spatial_shape": self.spatial_shape,
            "embedding": [[round(v, 6) for v in p] for p in self.embedding],
            "channel_means": [[round(v, 6) for v in c] for c in self.channel_means],
            "sample_ids": self.sample_ids,
            "attention": [a.to_dict() for a in self.attention],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActivationAtlas":
        return cls(
            model_name=data["model_name"],
            layer_name=data["layer_name"],
            spatial_shape=[int(v) for v in data.get("spatial_shape", [])],
            embedding=[[float(v) for v in p] for p in data.get("embedding", [])],
            channel_means=[[float(v) for v in c] for c in data.get("channel_means", [])],
            sample_ids=[str(s) for s in data.get("sample_ids", [])],
            attention=[AttentionMap.from_dict(a) for a in data.get("attention", [])],
        )


def resolve_model_adapter(name: str) -> Optional[Any]:
    """Map a live-model name to its nn.Module factory, lazily.

    The heavy models are import-optional: the host may run on a machine
    without the ASP submodule or the wrapper weights, in which case the
    adapter simply is not available and the caller charts previously
    exported artifacts instead. Nothing is imported until first called.
    """
    adapters = {
        "animestitchnet": ("submodules.ASP.backend.src.models.stitch_net", "AnimeStitchNet"),
        "birefnet": ("backend.src.models.wrappers.birefnet_wrapper", "BiRefNetWrapper"),
        "loftr": ("backend.src.models.wrappers.loftr_wrapper", "LoFTRWrapper"),
    }
    target = adapters.get(name.lower())
    if target is None:
        return None
    module_name, attr = target
    try:
        import importlib

        module = importlib.import_module(module_name)
        return getattr(module, attr, None)
    except Exception:
        return None


__all__ = [
    "ActivationAtlas",
    "AttentionMap",
    "EigenDensityBin",
    "HessianSpectrum",
    "LossSurface",
    "TrajectoryPoint",
    "TrajectoryProjection",
    "resolve_model_adapter",
]
