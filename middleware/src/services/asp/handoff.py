"""ASP result → HybridStitch handoff contract (issue #1088).

The benchmark harness already keeps a ``PipelineSession`` (frame list, global
affines, identity, fallback). The product Stitch tab needs the same snapshot
so a finished ASP run can be refined by hand in HybridStitch.

HybridStitch stores one homography per pair, and its solver uses
``cv2.findHomography(pts_a, pts_b)`` — that matrix maps frame-A pixels onto
frame B. ASP stores a global affine per frame into canvas space. For adjacent
frames those are the same alignment:

    p_canvas = A_a @ p_a = A_b @ p_b
    p_b = inv(A_b) @ A_a @ p_a

so the seeded matrix is ``inv(A_b) @ A_a``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from middleware.src.services.base import CommandValidationError

HANDOFF_KIND = "asp.hybrid_stitch"
HANDOFF_VERSION = 1
_SINGULAR_DET = 1e-8


class HandoffContractError(CommandValidationError):
    """The ASP result cannot be turned into a HybridStitch handoff."""


@dataclass(frozen=True)
class PairHomography:
    """One pairwise homography HybridStitch can seed and then edit.

    ``matrix`` maps frame ``index_a`` pixels onto frame ``index_b``.
    """

    index_a: int
    index_b: int
    matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "index_a": self.index_a,
            "index_b": self.index_b,
            "matrix": [list(row) for row in self.matrix],
        }


@dataclass(frozen=True)
class AspHybridHandoff:
    """Frames and alignment an ASP run gives HybridStitch for refinement."""

    image_paths: tuple[str, ...]
    output_path: str | None = None
    pair_homographies: tuple[PairHomography, ...] = ()
    identity: str | None = None
    fallback_reason: str | None = None
    source: str = "asp"

    def to_payload(self) -> dict[str, Any]:
        """JSON-safe snapshot safe to cross a Qt signal or a session file."""
        return {
            "kind": HANDOFF_KIND,
            "version": HANDOFF_VERSION,
            "image_paths": list(self.image_paths),
            "output_path": self.output_path,
            "pair_homographies": [pair.as_dict() for pair in self.pair_homographies],
            "identity": self.identity,
            "fallback_reason": self.fallback_reason,
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | AspHybridHandoff) -> AspHybridHandoff:
        """Parse a payload produced by :meth:`to_payload`."""
        if isinstance(payload, AspHybridHandoff):
            return payload
        if not isinstance(payload, Mapping):
            raise HandoffContractError("hybrid handoff payload must be an object", field="payload")
        kind = payload.get("kind")
        if kind != HANDOFF_KIND:
            raise HandoffContractError(
                f"hybrid handoff kind must be {HANDOFF_KIND!r}",
                field="kind",
            )
        version = payload.get("version", HANDOFF_VERSION)
        if version != HANDOFF_VERSION:
            raise HandoffContractError(
                f"unsupported hybrid handoff version {version!r}",
                field="version",
            )
        paths = _require_paths(payload.get("image_paths"))
        pairs = _parse_pairs(payload.get("pair_homographies") or (), len(paths))
        source = payload.get("source", "asp")
        if source != "asp":
            raise HandoffContractError("hybrid handoff source must be 'asp'", field="source")
        return cls(
            image_paths=paths,
            output_path=_optional_text(payload.get("output_path")),
            pair_homographies=pairs,
            identity=_optional_text(payload.get("identity")),
            fallback_reason=_optional_text(payload.get("fallback_reason")),
            source="asp",
        )


def build_hybrid_handoff(
    *,
    image_paths: Sequence[str],
    affines: Sequence[Any] | None = None,
    output_path: str | None = None,
    identity: str | None = None,
    fallback_reason: str | None = None,
) -> AspHybridHandoff:
    """Build a handoff from the frames ASP kept and their global affines.

    ``affines`` must be omitted or the same length as ``image_paths``. A
    length mismatch is a contract error: seeding a prefix would attach the
    wrong alignment to a frame. Individual singular affines are skipped so
    one bad pair does not drop the rest of the sequence.
    """
    paths = _require_paths(image_paths)
    pair_homographies: tuple[PairHomography, ...] = ()
    if affines is not None:
        affine_list = list(affines)
        if len(affine_list) != len(paths):
            raise HandoffContractError(
                f"affine count {len(affine_list)} does not match {len(paths)} frames",
                field="affines",
            )
        pair_homographies = pairwise_homographies_from_global_affines(affine_list)
    return AspHybridHandoff(
        image_paths=paths,
        output_path=_optional_text(output_path),
        pair_homographies=pair_homographies,
        identity=_optional_text(identity),
        fallback_reason=_optional_text(fallback_reason),
    )


def pairwise_homographies_from_global_affines(
    affines: Sequence[Any],
) -> tuple[PairHomography, ...]:
    """Adjacent-pair homographies in HybridStitch's A→B convention."""
    pairs: list[PairHomography] = []
    matrices = list(affines)
    for index in range(len(matrices) - 1):
        pair = _pair_from_globals(index, index + 1, matrices[index], matrices[index + 1])
        if pair is not None:
            pairs.append(pair)
    return tuple(pairs)


def handoff_from_session(session: Any) -> AspHybridHandoff:
    """Read kept frames, canvas affines, and identity off a pipeline session.

    Affines are attached only when their count matches the kept frame list
    (or, if nothing was marked dropped, the original input list). A count
    mismatch drops the alignment and still hands off the frames — a SCANS
    fallback often has no usable affine row.
    """
    paths, affines, output_path, identity, fallback_reason = _session_fields(session)
    try:
        return build_hybrid_handoff(
            image_paths=paths,
            affines=affines,
            output_path=output_path,
            identity=identity,
            fallback_reason=fallback_reason,
        )
    except HandoffContractError:
        if affines is None:
            raise
        return build_hybrid_handoff(
            image_paths=paths,
            affines=None,
            output_path=output_path,
            identity=identity,
            fallback_reason=fallback_reason,
        )


def hybrid_handoff_payload(source: Any) -> dict[str, Any] | None:
    """Payload for a pipeline (session or legacy state) or a bare session.

    Returns ``None`` when ``source`` is not a finished ASP run. MagicMock-style
    placeholders and an unset ``last_session`` stay ``None``.
    """
    own_paths = getattr(getattr(source, "inputs", None), "image_paths", None)
    session = source if isinstance(own_paths, (list, tuple)) else getattr(source, "last_session", None)
    paths = getattr(getattr(session, "inputs", None), "image_paths", None)
    if isinstance(paths, (list, tuple)) and len(paths) >= 2:
        try:
            return handoff_from_session(session).to_payload()
        except HandoffContractError:
            return None
    state = getattr(source, "_hybrid_handoff_state", None)
    if not isinstance(state, dict):
        return None
    try:
        return build_hybrid_handoff(
            image_paths=state.get("image_paths") or (),
            affines=state.get("affines"),
            output_path=state.get("output_path"),
            identity=state.get("identity"),
            fallback_reason=state.get("fallback_reason"),
        ).to_payload()
    except HandoffContractError:
        return None


def handoff_summary(handoff: AspHybridHandoff) -> str:
    """Confirmation copy for the Stitch tab after it switches to Hybrid Stitch."""
    n_frames = len(handoff.image_paths)
    lines = [f"Loaded {n_frames} frame(s) into Hybrid Stitch."]
    n_pairs = len(handoff.pair_homographies)
    if n_pairs:
        noun = "alignment" if n_pairs == 1 else "alignments"
        lines.append(
            f"Seeded {n_pairs} adjacent {noun} from the ASP result. "
            "Load a pair to refine control points, seams, and warp."
        )
    else:
        lines.append("ASP did not produce a usable alignment. Place control points for each pair.")
    if handoff.fallback_reason:
        lines.append(f"ASP fallback: {handoff.fallback_reason}.")
    if handoff.output_path:
        lines.append(f"Panorama: {handoff.output_path}")
    return "\n".join(lines)


def _session_fields(
    session: Any,
) -> tuple[list[str], list[Any] | None, str | None, str | None, str | None]:
    inputs = getattr(session, "inputs", None)
    original = [str(path) for path in (getattr(inputs, "image_paths", None) or []) if str(path)]
    provenance = list(getattr(session, "frame_provenance", None) or [])
    kept = [
        str(row.get("path"))
        for row in provenance
        if isinstance(row, Mapping) and row.get("kept", True) and row.get("path")
    ]
    paths = kept or original
    artifacts = getattr(session, "artifacts", None)
    affines: list[Any] | None = None
    output_path = _optional_text(getattr(inputs, "output_path", None))
    if isinstance(artifacts, Mapping):
        raw_affines = artifacts.get("affines")
        if isinstance(raw_affines, (list, tuple)) and len(raw_affines) > 0:
            affines = list(raw_affines)
        artifact_output = _optional_text(artifacts.get("output_path"))
        if artifact_output:
            output_path = artifact_output
    if affines is not None and len(affines) != len(paths):
        if len(original) == len(affines):
            paths = original
        else:
            affines = None
    identity = _optional_text(_enum_text(getattr(session, "identity", None)))
    fallback_reason = _optional_text(_enum_text(getattr(session, "fallback_reason", None)))
    if fallback_reason is None:
        fallbacks = list(getattr(session, "fallbacks", None) or [])
        if fallbacks and isinstance(fallbacks[-1], Mapping):
            fallback_reason = _optional_text(fallbacks[-1].get("reason"))
    return paths, affines, output_path, identity, fallback_reason


def _pair_from_globals(
    index_a: int,
    index_b: int,
    affine_a: Any,
    affine_b: Any,
) -> PairHomography | None:
    try:
        matrix_a = _as_3x3(affine_a)
        matrix_b = _as_3x3(affine_b)
    except HandoffContractError:
        return None
    if abs(float(np.linalg.det(matrix_b))) < _SINGULAR_DET:
        return None
    try:
        mapped = np.linalg.inv(matrix_b) @ matrix_a
    except np.linalg.LinAlgError:
        return None
    if mapped.shape != (3, 3) or not np.isfinite(mapped).all():
        return None
    return PairHomography(index_a, index_b, _freeze_matrix(mapped))


def _as_3x3(matrix: Any) -> np.ndarray:
    try:
        array = np.asarray(matrix, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise HandoffContractError("affine is not a numeric matrix", field="affines") from exc
    if array.shape == (2, 3):
        promoted = np.eye(3, dtype=np.float64)
        promoted[:2, :] = array
        return promoted
    if array.shape == (3, 3):
        return array
    raise HandoffContractError(
        f"affine shape {array.shape} is not 2x3 or 3x3",
        field="affines",
    )


def _freeze_matrix(
    array: np.ndarray,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    return (
        (float(array[0, 0]), float(array[0, 1]), float(array[0, 2])),
        (float(array[1, 0]), float(array[1, 1]), float(array[1, 2])),
        (float(array[2, 0]), float(array[2, 1]), float(array[2, 2])),
    )


def _require_paths(image_paths: Any) -> tuple[str, ...]:
    if isinstance(image_paths, (str, bytes)) or not isinstance(image_paths, Sequence):
        raise HandoffContractError("image_paths must be a sequence of paths", field="image_paths")
    paths = tuple(str(path) for path in image_paths)
    if len(paths) < 2:
        raise HandoffContractError("Hybrid Stitch handoff needs at least two frames", field="image_paths")
    if any(not path.strip() for path in paths):
        raise HandoffContractError("image_paths contains an empty path", field="image_paths")
    return paths


def _parse_pairs(raw_pairs: Any, n_frames: int) -> tuple[PairHomography, ...]:
    if isinstance(raw_pairs, (str, bytes)) or not isinstance(raw_pairs, Sequence):
        raise HandoffContractError("pair_homographies must be a list", field="pair_homographies")
    pairs: list[PairHomography] = []
    seen: set[tuple[int, int]] = set()
    for raw in raw_pairs:
        if not isinstance(raw, Mapping):
            raise HandoffContractError("pair homography must be an object", field="pair_homographies")
        try:
            index_a = int(raw["index_a"])
            index_b = int(raw["index_b"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HandoffContractError("pair homography is missing frame indexes", field="pair_homographies") from exc
        if not (0 <= index_a < index_b < n_frames):
            raise HandoffContractError(
                f"pair ({index_a}, {index_b}) is outside {n_frames} frames",
                field="pair_homographies",
            )
        key = (index_a, index_b)
        if key in seen:
            raise HandoffContractError(f"duplicate pair {key}", field="pair_homographies")
        seen.add(key)
        try:
            matrix = _as_3x3(raw["matrix"])
        except (KeyError, HandoffContractError) as exc:
            raise HandoffContractError("pair homography matrix must be 3x3", field="matrix") from exc
        if not np.isfinite(matrix).all():
            raise HandoffContractError("pair homography matrix must be finite", field="matrix")
        pairs.append(PairHomography(index_a, index_b, _freeze_matrix(matrix)))
    return tuple(pairs)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _enum_text(value)
    if text is None:
        return None
    stripped = str(text).strip()
    return stripped or None


def _enum_text(value: Any) -> Any:
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return value


__all__ = [
    "HANDOFF_KIND",
    "HANDOFF_VERSION",
    "AspHybridHandoff",
    "HandoffContractError",
    "PairHomography",
    "build_hybrid_handoff",
    "handoff_from_session",
    "handoff_summary",
    "hybrid_handoff_payload",
    "pairwise_homographies_from_global_affines",
]
