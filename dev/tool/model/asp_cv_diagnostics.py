"""ASP Stage-by-Stage CV Diagnostics models (Track B Phase 3, issue #395).

Host attachment: plugin + ``PipelineSession`` ``TelemetrySink``. Consumes
the existing OTLP-shaped JSONL telemetry emitted by
``submodules/ASP/backend/src/core/pipeline/telemetry.py`` and produces
diagnostic artifacts for the Rerun desktop sidecar.

This module defines serializable dataclasses for:
- Feature match geometry (keypoints, inliers, fundamental matrix residuals)
- Bundle adjustment residuals (reprojection errors before/after GNC-TLS)
- Seam blending diagnostics (spatial routing, frequency profiles, gradient coherence)

No rerun-sdk or opentelemetry import here — those are in the plugin entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Keypoint:
    """A 2D keypoint with optional scale/orientation."""

    x: float
    y: float
    scale: float = 1.0
    orientation: float = 0.0
    response: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "scale": self.scale,
            "orientation": self.orientation,
            "response": self.response,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Keypoint":
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            scale=float(data.get("scale", 1.0)),
            orientation=float(data.get("orientation", 0.0)),
            response=float(data.get("response", 0.0)),
        )


@dataclass
class FeatureMatch:
    """A match between two keypoints across frames."""

    query_idx: int
    train_idx: int
    distance: float
    is_inlier: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_idx": self.query_idx,
            "train_idx": self.train_idx,
            "distance": self.distance,
            "is_inlier": self.is_inlier,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureMatch":
        return cls(
            query_idx=int(data["query_idx"]),
            train_idx=int(data["train_idx"]),
            distance=float(data["distance"]),
            is_inlier=bool(data.get("is_inlier", False)),
        )


@dataclass
class MatchGeometry:
    """Feature matching diagnostics for a frame pair.

    Captures keypoints, matches, inlier mask, and the estimated
    fundamental matrix / homography with residual statistics.
    """

    frame_a_id: str
    frame_b_id: str
    keypoints_a: List[Keypoint] = field(default_factory=list)
    keypoints_b: List[Keypoint] = field(default_factory=list)
    matches: List[FeatureMatch] = field(default_factory=list)
    inlier_count: int = 0
    fundamental_matrix: Optional[List[List[float]]] = None  # 3x3 row-major
    homography: Optional[List[List[float]]] = None  # 3x3 row-major
    residual_mean: float = 0.0
    residual_std: float = 0.0
    residual_max: float = 0.0

    @property
    def inlier_ratio(self) -> float:
        if not self.matches:
            return 0.0
        return self.inlier_count / len(self.matches)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_a_id": self.frame_a_id,
            "frame_b_id": self.frame_b_id,
            "keypoints_a": [k.to_dict() for k in self.keypoints_a],
            "keypoints_b": [k.to_dict() for k in self.keypoints_b],
            "matches": [m.to_dict() for m in self.matches],
            "inlier_count": self.inlier_count,
            "inlier_ratio": self.inlier_ratio,
            "fundamental_matrix": self.fundamental_matrix,
            "homography": self.homography,
            "residual_mean": self.residual_mean,
            "residual_std": self.residual_std,
            "residual_max": self.residual_max,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatchGeometry":
        return cls(
            frame_a_id=data["frame_a_id"],
            frame_b_id=data["frame_b_id"],
            keypoints_a=[Keypoint.from_dict(k) for k in data.get("keypoints_a", [])],
            keypoints_b=[Keypoint.from_dict(k) for k in data.get("keypoints_b", [])],
            matches=[FeatureMatch.from_dict(m) for m in data.get("matches", [])],
            inlier_count=int(data.get("inlier_count", 0)),
            fundamental_matrix=data.get("fundamental_matrix"),
            homography=data.get("homography"),
            residual_mean=float(data.get("residual_mean", 0.0)),
            residual_std=float(data.get("residual_std", 0.0)),
            residual_max=float(data.get("residual_max", 0.0)),
        )


@dataclass
class BundleAdjustmentResiduals:
    """Reprojection errors before and after GNC-TLS bundle adjustment.

    ASP BA is a 2D affine/translation chain, not a calibrated pinhole
    reconstruct. Camera origins are on the canvas plane, inliers lifted
    to z=0 for visualization. Every viewer caption must say so.
    """

    stage_name: str
    frame_ids: List[str] = field(default_factory=list)
    residuals_before: List[float] = field(default_factory=list)
    residuals_after: List[float] = field(default_factory=list)
    camera_origins: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def mean_before(self) -> float:
        if not self.residuals_before:
            return 0.0
        return sum(self.residuals_before) / len(self.residuals_before)

    @property
    def mean_after(self) -> float:
        if not self.residuals_after:
            return 0.0
        return sum(self.residuals_after) / len(self.residuals_after)

    @property
    def improvement_factor(self) -> float:
        if self.mean_after == 0:
            return 0.0
        return self.mean_before / self.mean_after

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "frame_ids": self.frame_ids,
            "residuals_before": self.residuals_before,
            "residuals_after": self.residuals_after,
            "mean_before": self.mean_before,
            "mean_after": self.mean_after,
            "improvement_factor": self.improvement_factor,
            "camera_origins": [list(o) for o in self.camera_origins],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BundleAdjustmentResiduals":
        return cls(
            stage_name=data["stage_name"],
            frame_ids=data.get("frame_ids", []),
            residuals_before=data.get("residuals_before", []),
            residuals_after=data.get("residuals_after", []),
            camera_origins=[tuple(o) for o in data.get("camera_origins", [])],
        )


@dataclass
class SeamFrequencyProfile:
    """FFT spatial-frequency profile along a seam boundary.

    References ``_seam_freq_profile`` in ``compositing.py``.
    """

    seam_id: str
    frequencies: List[float] = field(default_factory=list)
    magnitudes_low: List[float] = field(default_factory=list)
    magnitudes_high: List[float] = field(default_factory=list)
    mismatch_score: float = 0.0  # higher = worse blending

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seam_id": self.seam_id,
            "frequencies": self.frequencies,
            "magnitudes_low": self.magnitudes_low,
            "magnitudes_high": self.magnitudes_high,
            "mismatch_score": self.mismatch_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeamFrequencyProfile":
        return cls(
            seam_id=data["seam_id"],
            frequencies=data.get("frequencies", []),
            magnitudes_low=data.get("magnitudes_low", []),
            magnitudes_high=data.get("magnitudes_high", []),
            mismatch_score=float(data.get("mismatch_score", 0.0)),
        )


@dataclass
class SeamGradientCoherence:
    """Sobel gradient-direction coherence vectors across a seam.

    Circular distance ``d_c(∇a, ∇b) = 1 - cos(∇a - ∇b)`` rendered as
    a heatmap highlights photometric tearing regions.
    """

    seam_id: str
    positions: List[Tuple[float, float]] = field(default_factory=list)
    gradient_a: List[float] = field(default_factory=list)  # radians
    gradient_b: List[float] = field(default_factory=list)  # radians
    coherence: List[float] = field(default_factory=list)  # [0, 2]

    @property
    def mean_coherence(self) -> float:
        if not self.coherence:
            return 0.0
        return sum(self.coherence) / len(self.coherence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seam_id": self.seam_id,
            "positions": [list(p) for p in self.positions],
            "gradient_a": self.gradient_a,
            "gradient_b": self.gradient_b,
            "coherence": self.coherence,
            "mean_coherence": self.mean_coherence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeamGradientCoherence":
        return cls(
            seam_id=data["seam_id"],
            positions=[tuple(p) for p in data.get("positions", [])],
            gradient_a=data.get("gradient_a", []),
            gradient_b=data.get("gradient_b", []),
            coherence=data.get("coherence", []),
        )


@dataclass
class SeamDiagnostic:
    """Combined seam blending diagnostics for one seam boundary."""

    seam_id: str
    source_frame_a: str
    source_frame_b: str
    routing_path: List[Tuple[float, float]] = field(default_factory=list)
    frequency_profile: Optional[SeamFrequencyProfile] = None
    gradient_coherence: Optional[SeamGradientCoherence] = None
    cut_energy: float = 0.0  # from asp.seam.cut_energy metric

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seam_id": self.seam_id,
            "source_frame_a": self.source_frame_a,
            "source_frame_b": self.source_frame_b,
            "routing_path": [list(p) for p in self.routing_path],
            "frequency_profile": self.frequency_profile.to_dict() if self.frequency_profile else None,
            "gradient_coherence": self.gradient_coherence.to_dict() if self.gradient_coherence else None,
            "cut_energy": self.cut_energy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeamDiagnostic":
        return cls(
            seam_id=data["seam_id"],
            source_frame_a=data["source_frame_a"],
            source_frame_b=data["source_frame_b"],
            routing_path=[tuple(p) for p in data.get("routing_path", [])],
            frequency_profile=(
                SeamFrequencyProfile.from_dict(data["frequency_profile"]) if data.get("frequency_profile") else None
            ),
            gradient_coherence=(
                SeamGradientCoherence.from_dict(data["gradient_coherence"]) if data.get("gradient_coherence") else None
            ),
            cut_energy=float(data.get("cut_energy", 0.0)),
        )


@dataclass
class StageDiagnosticReport:
    """Full diagnostic report for one pipeline run.

    Aggregates feature matching, bundle adjustment, and seam diagnostics
    for visualization in the Rerun desktop sidecar.
    """

    session_id: str
    match_geometries: List[MatchGeometry] = field(default_factory=list)
    ba_residuals: List[BundleAdjustmentResiduals] = field(default_factory=list)
    seam_diagnostics: List[SeamDiagnostic] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "match_geometries": [m.to_dict() for m in self.match_geometries],
            "ba_residuals": [b.to_dict() for b in self.ba_residuals],
            "seam_diagnostics": [s.to_dict() for s in self.seam_diagnostics],
            "summary": {
                "total_matches": sum(len(m.matches) for m in self.match_geometries),
                "total_inliers": sum(m.inlier_count for m in self.match_geometries),
                "mean_inlier_ratio": (
                    sum(m.inlier_ratio for m in self.match_geometries) / len(self.match_geometries)
                    if self.match_geometries
                    else 0.0
                ),
                "ba_improvement": (
                    sum(b.improvement_factor for b in self.ba_residuals) / len(self.ba_residuals)
                    if self.ba_residuals
                    else 0.0
                ),
                "mean_seam_coherence": (
                    sum(s.gradient_coherence.mean_coherence for s in self.seam_diagnostics if s.gradient_coherence)
                    / sum(1 for s in self.seam_diagnostics if s.gradient_coherence)
                    if any(s.gradient_coherence for s in self.seam_diagnostics)
                    else 0.0
                ),
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StageDiagnosticReport":
        return cls(
            session_id=data["session_id"],
            match_geometries=[MatchGeometry.from_dict(m) for m in data.get("match_geometries", [])],
            ba_residuals=[BundleAdjustmentResiduals.from_dict(b) for b in data.get("ba_residuals", [])],
            seam_diagnostics=[SeamDiagnostic.from_dict(s) for s in data.get("seam_diagnostics", [])],
        )


__all__ = [
    "BundleAdjustmentResiduals",
    "FeatureMatch",
    "Keypoint",
    "MatchGeometry",
    "SeamDiagnostic",
    "SeamFrequencyProfile",
    "SeamGradientCoherence",
    "StageDiagnosticReport",
]
