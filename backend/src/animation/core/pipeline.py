"""
AnimeStitchPipeline — top-level orchestrator.

Delegates each pipeline stage to its sibling module (matching, photometric,
masking, ECC, rendering, compositing, canvas, bundle adjustment).
"""

from __future__ import annotations

import contextlib
import gc

# §3.14 — Heavy model wrapper imports are deferred to first use.
# Each module-level try/except was loading kornia/transformers/torchvision at pytest
# collection time, contributing to the test-suite freeze (S140 root causes).
# We probe availability cheaply with importlib.util.find_spec(); the actual class
# is imported inside the method that instantiates it.
import importlib.util as _importlib_util_pipeline
import logging
import os
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine
from backend.src.animation.alignment.canvas import (
    _compute_canvas,
    _crop_to_valid,
    _detect_scroll_axis,
    _load_frames,
    _normalise_widths,
    _panorama_stitch_fallback,
    _scan_stitch_fallback,
    _telea_fill_gaps,
    find_optimal_sequence,
)
from backend.src.animation.alignment.ecc import _ecc_refine
from backend.src.animation.alignment.matching import (
    _match_pair,
    _pairwise_match,
    _phase_correlate,
    _sample_bg_points,
    _template_match,
)
from backend.src.animation.core.validation import (
    _compute_adaptive_min_gap,
    _compute_adaptive_rot_scale,
    _validate_affines,
)
from backend.src.animation.ingestion.masking import (
    _cleanup_sam2_state,
    _compute_fg_masks,
    _compute_fg_masks_sam2_stateful,
)
from backend.src.animation.rendering.compositing import (
    _composite_foreground,
)
from backend.src.animation.rendering.photometric import _apply_basic, _correct_vignetting
from backend.src.animation.rendering.rendering import (
    _cluster_animation_phases,
    _render,
    _render_first,
    _render_laplacian,
    _render_median,
)
from backend.src.constants import (
    ADAPTIVE_MIN_DISP_FRAC,
    HIGH_CONF_EDGE_THRESH,
    LAPLACIAN_BANDS,
    MATCH_EDGE_CROP,
    MIN_EXPECTED_STEP,
    NEAR_DUP_LUMA_THRESH,
    SPATIAL_DEDUP_PX,
    STATIC_EDGE_MIN_DISP_PX,
)
from backend.src.errors import (
    CanvasError,
    PipelineError,
)

if TYPE_CHECKING:
    from backend.src.models.core.stitch_net import AnimeStitchNet
    from backend.src.models.wrappers.aliked_lg_wrapper import ALIKEDLightGlueWrapper
    from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper
    from backend.src.models.wrappers.efficient_loftr_wrapper import EfficientLoFTRWrapper
    from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper

logger = logging.getLogger(__name__)

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

try:
    try:
        import base as _batch
    except ImportError:
        from backend.src.animation import base as _batch

    if getattr(_batch, "__file__", None) is None:
        raise ImportError("base is a namespace package, not the compiled extension")
    _HAS_BATCH: bool = True
except ImportError:
    _batch = None  # type: ignore[assignment]
    _HAS_BATCH: bool = False

# BaSiCWrapper only uses cv2/numpy/torch — safe to import at module level.
try:
    from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

    _BASIC_OK = True
except ImportError:
    _BASIC_OK = False

# birefnet_wrapper → transformers; kornia wrappers → kornia+torchvision; EfficientLoFTR → transformers
_BIREFNET_OK: bool = _importlib_util_pipeline.find_spec("transformers") is not None
_LOFTR_OK: bool = _importlib_util_pipeline.find_spec("kornia") is not None
_ELOFTR_OK: bool = _importlib_util_pipeline.find_spec("transformers") is not None
_ALIKED_OK: bool = _importlib_util_pipeline.find_spec("kornia") is not None

# roma_wrapper: romatch library (not typically installed)
try:
    from backend.src.models.wrappers.roma_wrapper import RoMaWrapper

    _ROMA_OK = True
except ImportError:
    _ROMA_OK = False

try:
    from backend.src.animation.flow.flow_refine import _flow_refine, _load_sea_raft

    _SEA_RAFT_OK = True
except ImportError:
    _SEA_RAFT_OK = False

# §4.7 — dy_cv pre-detection gate.
# Coefficient of variation of adjacent vertical frame steps.  When dy_cv ≥ threshold
# the pipeline immediately falls back to SCANS before expensive ARAP/BiRefNet work.
# 97-test benchmark: dy_cv ≥ 1.5 → catastrophic ASP failure (AlSSIM −22 to −37%,
# seam_vis 60–120 vs SCANS 2–3) while SCANS handles these sequences trivially.
# Default 1.5 (enabled). Set ASP_DY_CV_MAX=0 to disable.
_DY_CV_MAX: float = float(os.environ.get("ASP_DY_CV_MAX", "1.5"))
_USE_SAM2: bool = os.environ.get("ASP_USE_SAM2", "0") != "0"


def _reject_static_edges(
    edges: List[Dict],
    min_disp_px: float = STATIC_EDGE_MIN_DISP_PX,
) -> List[Dict]:
    """§1.2A — Drop edges where |dx| < min_disp_px AND |dy| < min_disp_px.

    Rejects near-zero-2D-displacement matches for ALL edges (adjacent and
    skip-frame).  When such edges survive into bundle adjustment they anchor
    two frames at essentially the same canvas position, corrupting the global
    translation estimate for the rest of the sequence.

    A match is kept if EITHER axis displacement meets or exceeds the threshold,
    so valid diagonal-scroll edges (large |dx|, small |dy|) are preserved.
    """
    return [
        e
        for e in edges
        if abs(float(e["M"][0, 2])) >= min_disp_px
        or abs(float(e["M"][1, 2])) >= min_disp_px
    ]


def _compute_adaptive_min_disp(edges: List[Dict]) -> float:
    """§1.2C — Content-adaptive minimum displacement threshold.

    Estimates the expected inter-frame step from the median of adjacent-edge
    displacements on the dominant scroll axis and returns
    ``max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC * expected_step)``.

    For typical scroll sequences the floor dominates (step ≤ 500 px → 10% ≤
    50 px).  For high-resolution or fast-scroll content the adaptive value
    exceeds the floor and provides proportionally stronger rejection (e.g.,
    1 000 px/frame → threshold 100 px instead of 50 px).
    """
    adj_edges = [e for e in edges if e["j"] == e["i"] + 1]
    if not adj_edges:
        return float(STATIC_EDGE_MIN_DISP_PX)

    adx = np.array([abs(float(e["M"][0, 2])) for e in adj_edges])
    ady = np.array([abs(float(e["M"][1, 2])) for e in adj_edges])
    disps = adx if float(np.median(adx)) >= float(np.median(ady)) else ady

    expected_step = float(np.median(disps))
    return max(float(STATIC_EDGE_MIN_DISP_PX), ADAPTIVE_MIN_DISP_FRAC * expected_step)


def _filter_high_conf_edges(
    edges: List[Dict],
    min_weight: float = HIGH_CONF_EDGE_THRESH,
) -> List[Dict]:
    """§2.9C — Keep only edges whose match weight meets the high-confidence floor.

    LoFTR edges typically have ``weight`` in [0.7, 0.95]; template-match and
    phase-correlation fallbacks land in [0.15, 0.55].  When bundle adjustment
    produces a bad ratio (one outlier edge pulling frames together), filtering
    to high-confidence edges removes the low-quality fallback edges that are
    most likely to be wrong.

    Used as a pre-check before the existing Retry-1 (adjacent-only) path: if
    at least ``N-1`` high-confidence edges survive, re-solve the bundle.  If
    fewer survive, fall through to Retry 1 unchanged — no information is lost.
    """
    return [e for e in edges if float(e.get("weight", 0.0)) >= min_weight]


def _check_edge_graph_connectivity(
    edges: List[Dict],
    n_frames: int,
) -> bool:
    """§1.15: Return True iff all frames 0..n_frames-1 are in one connected component.

    Uses iterative path-compression Union-Find (same algorithm as §1.1B spanning
    tree) to check graph connectivity after all edge filters have run.  A
    disconnected graph fed into bundle adjustment assigns wrong translations to
    isolated frames — catching this before BA allows an immediate fallback rather
    than a corrupt solve followed by a downstream validation failure.

    Trivially returns True when *n_frames* ≤ 1 (nothing to connect) or when
    *n_frames* − 1 edges already span all nodes (lower bound for connectivity).
    """
    if n_frames <= 1:
        return True

    parent = list(range(n_frames))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        ei, ej = int(e.get("i", -1)), int(e.get("j", -1))
        if not (0 <= ei < n_frames and 0 <= ej < n_frames):
            continue
        pi, pj = _find(ei), _find(ej)
        if pi != pj:
            parent[pi] = pj

    root = _find(0)
    return all(_find(f) == root for f in range(n_frames))


def _sort_frames_by_index(paths: List[str]) -> List[str]:
    """§1.63: Sort frame paths by numeric suffix extracted from the filename (S127).

    Frame file names produced by video extraction tools (FFmpeg, OpenCV) are
    typically ``frame_00001.png``, ``frame_00002.png``, etc.  When the caller
    discovers frames via ``glob()`` on some file systems (e.g. ext4 with dir_index)
    the OS-level directory order may not be numeric.  An out-of-order frame list
    causes the pipeline to treat consecutive file-system neighbours as adjacent
    camera positions, producing nonsensical phase-correlation displacements,
    reversed scroll direction, and incorrect BA edge graphs.

    This function re-sorts *paths* by the rightmost contiguous digit run in the
    stem (filename without extension).  When no digit run is found for a path,
    that path is sorted by its original index in *paths* (stable), placing it
    after all numerically-indexed paths.  This keeps the behaviour predictable
    for mixed-name directories while avoiding an import of ``natsort``.

    Parameters
    ----------
    paths : list of file paths to sort.

    Returns
    -------
    list[str]
        New list in ascending numeric-suffix order.  If all stems lack a digit
        suffix (e.g. user-supplied paths with descriptive names), the original
        order is returned unchanged.
    """
    # relocated: import re

    def _key(p: str) -> tuple:
        stem = os.path.splitext(os.path.basename(p))[0]
        m = re.search(r"(\d+)$", stem)
        return (0, int(m.group(1))) if m else (1, 0)

    sorted_paths = sorted(paths, key=_key)
    return sorted_paths


def _compute_dy_cv(affines: List[np.ndarray]) -> float:
    """§4.7: Coefficient of variation of adjacent vertical frame steps.

    Computes ``std(|Δty|) / mean(|Δty|)`` from the bundle-adjusted affines.
    A high dy_cv indicates an irregular scroll pattern (variable step sizes)
    where ASP's compositing assumptions break down.

    97-test benchmark (S160, 2026-06-23): dy_cv ≥ 1.5 → catastrophic ASP
    failure on every test in that regime (AlSSIM −22 to −37%, seam_vis
    60–120 vs SCANS 2–3).  SCANS handles these sequences trivially because
    it requires no frame-to-frame registration.

    Returns 0.0 when N < 2 (gate will not fire).

    Parameters
    ----------
    affines:
        List of N 2×3 float32 affine matrices from bundle adjustment.

    Returns
    -------
    float
        dy_cv ≥ 0.  Zero when N < 2.
    """
    N = len(affines)
    if N < 2:
        return 0.0
    dy_steps = [abs(float(affines[k][1, 2]) - float(affines[k - 1][1, 2])) for k in range(1, N)]
    mean_dy = float(np.mean(dy_steps))
    if mean_dy < 1.0:
        return 0.0
    return float(np.std(dy_steps)) / mean_dy


def _compute_adaptive_dy_cv_max(n_frames: int, base_max: float = 1.5) -> float:
    """§5.8: Lower dy_cv ceiling for sequences with many frames.

    With N≥8 frames, step irregularity compounds across more seams.
    Scale: max(base_max * 8 / max(n_frames, 8), 0.8)
    - N=8: base_max (no change, floor ≥0.8)
    - N=16: base_max * 0.5 = 0.75 (→ floor 0.8)
    - N=4: base_max (unchanged, below 8)
    """
    if n_frames < 8:
        return base_max
    return max(base_max * 8.0 / n_frames, 0.8)


def _spatial_dedup_frames(
    frames: List[np.ndarray],
    scans_frames: List[np.ndarray],
    bg_masks: List[np.ndarray],
    image_paths: List[str],
    edges: List[dict],
    min_displacement_px: float,
) -> Tuple[
    List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str], List[dict], int
]:
    """One pass of spatial near-static frame dedup (§1.9A).

    Identifies adjacent frames (j = i+1 in current edge list) whose
    measured displacement is below ``min_displacement_px`` on the dominant
    scroll axis and removes them.  ``scans_frames`` is kept synchronised
    with ``frames`` so every SCANS fallback path uses the same frame
    subset as the main compositing branch — eliminating the desync
    that previously caused the fallback to receive near-duplicate frames
    the compositor had already discarded.

    Returns ``(frames, scans_frames, bg_masks, image_paths, edges, n_dropped)``.
    When ``n_dropped == 0`` all lists are returned unchanged (no allocation).
    """
    adj_m: dict = {e["j"]: e for e in edges if e["j"] == e["i"] + 1}
    if not adj_m:
        return frames, scans_frames, bg_masks, image_paths, edges, 0

    if _HAS_BATCH and hasattr(_batch, "frame_selection"):
        try:
            # Convert M-affine edges to dx/dy format for C++ function
            dx_dy_edges = [
                {"i": e["i"], "j": e["j"], "dx": float(e["M"][0, 2]), "dy": float(e["M"][1, 2])}
                for e in edges
            ]
            keep_idx_raw = list(
                _batch.frame_selection.spatial_dedup_frames(
                    frames, scans_frames or [], bg_masks, image_paths,
                    dx_dy_edges, float(min_displacement_px),
                )
            )
            keep_idx = [int(i) for i in keep_idx_raw]
            if len(keep_idx) == len(frames):
                return frames, scans_frames, bg_masks, image_paths, edges, 0
            o2n: dict = {old: new for new, old in enumerate(keep_idx)}
            drop_set = set(range(len(frames))) - set(keep_idx)
            new_edges = [
                {**e, "i": o2n[e["i"]], "j": o2n[e["j"]]}
                for e in edges
                if e["i"] not in drop_set and e["j"] not in drop_set
            ]
            return (
                [frames[i] for i in keep_idx],
                [scans_frames[i] for i in keep_idx] if scans_frames else [],
                [bg_masks[i] for i in keep_idx],
                [image_paths[i] for i in keep_idx],
                new_edges,
                len(drop_set),
            )
        except Exception:
            pass

    adx = [abs(float(e["M"][0, 2])) for e in adj_m.values()]
    ady = [abs(float(e["M"][1, 2])) for e in adj_m.values()]
    spa_axis = 0 if float(np.median(adx)) > float(np.median(ady)) else 1

    drop: set = set()
    for jj in sorted(adj_m):
        ee = adj_m[jj]
        if ee["i"] in drop:
            continue
        if abs(float(ee["M"][spa_axis, 2])) < min_displacement_px:
            drop.add(jj)

    if not drop:
        return frames, scans_frames, bg_masks, image_paths, edges, 0

    N = len(frames)
    keep_idx = [i for i in range(N) if i not in drop]
    o2n: dict = {old: new for new, old in enumerate(keep_idx)}
    new_edges = [
        {**e, "i": o2n[e["i"]], "j": o2n[e["j"]]}
        for e in edges
        if e["i"] not in drop and e["j"] not in drop
    ]
    return (
        [frames[i] for i in keep_idx],
        [scans_frames[i] for i in keep_idx] if scans_frames else [],  # §1.9A/§1.9C
        [bg_masks[i] for i in keep_idx],
        [image_paths[i] for i in keep_idx],
        new_edges,
        len(drop),
    )


def _reload_scans_frames(paths: List[str]) -> List[np.ndarray]:
    """§1.9C: Reload and width-normalise original frames from disk on demand.

    Called only when a SCANS/PANORAMA fallback actually fires and
    ``_SCANS_RELOAD=True``, so the Stage-2 snapshot allocation is avoided for
    the common (success) path.  ``paths`` is already synchronised with the
    live frame list by §1.9A spatial dedup, so the reloaded set matches what
    the pipeline was working with when it failed.
    """
    loaded = _load_frames(paths)
    if not loaded:
        return []
    return _normalise_widths(loaded)


def _compute_row_coverage(
    affines: list,
    frames: list,
    canvas_h: int,
) -> tuple:
    """
    Compute per-row frame coverage for the multi-frame canvas coverage gate.

    Returns
    -------
    (row_cov, pct_multi, median_cov) where:
      row_cov    : (canvas_h,) int32 — number of frames covering each row
      pct_multi  : fraction of content rows with ≥2-frame coverage (0–1)
      median_cov : median coverage among content rows
    """
    row_cov = np.zeros(canvas_h, dtype=np.int32)
    for _aff, _frame in zip(affines, frames, strict=False):
        _r0 = max(0, round(float(_aff[1, 2])))
        _r1 = min(canvas_h, _r0 + _frame.shape[0])
        if _r1 > _r0:
            row_cov[_r0:_r1] += 1
    content_rows = row_cov > 0
    n_content = int(content_rows.sum())
    if n_content == 0:
        return row_cov, 0.0, 0.0
    n_multi = int((row_cov[content_rows] >= 2).sum())
    pct_multi = n_multi / n_content
    median_cov = float(np.median(row_cov[content_rows]))
    return row_cov, pct_multi, median_cov


def _apply_hires_keyframes(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    hires_keyframes: Dict[int, str],
) -> Tuple[int, List[np.ndarray], List[np.ndarray], List[Optional[np.ndarray]]]:
    """
    Replace proxy frames with hires counterparts and scale affines/masks.

    Issue 9C (Sprint 8) — Hybrid 4K/1080p compositing.

    All heavy computation (phases 1–8: photometric correction, masking, matching,
    BA, ECC) ran at proxy (1080p) resolution. This function:
    1. Loads hires frames for the indices listed in *hires_keyframes*.
    2. Determines the (scale_y, scale_x) factor from the first successfully
       loaded hires frame vs. its proxy counterpart.
    3. Scales affine translation components (tx, ty) by (scale_x, scale_y).
       The linear sub-matrix (rotation/scale/shear) is dimensionless and unchanged.
    4. For frame indices NOT in hires_keyframes, bicubic-upscales the proxy.
    5. Resizes all bg_masks to match the hires frame dimensions.

    Returns (n_loaded, frames_hires, affines_scaled, masks_resized).
    When n_loaded == 0 all inputs are returned unchanged.
    """
    hires_imgs: Dict[int, np.ndarray] = {}
    for idx, path in hires_keyframes.items():
        if 0 <= idx < len(frames):
            img = cv2.imread(path)
            if img is not None:
                hires_imgs[idx] = img

    if not hires_imgs:
        return 0, frames, affines, bg_masks

    ref_idx = next(iter(hires_imgs))
    hires_h, hires_w = hires_imgs[ref_idx].shape[:2]
    proxy_h, proxy_w = frames[ref_idx].shape[:2]
    if proxy_h == 0 or proxy_w == 0:
        return 0, frames, affines, bg_masks

    scale_y = hires_h / proxy_h
    scale_x = hires_w / proxy_w

    affines_scaled = []
    for a in affines:
        a_new = a.copy().astype(np.float64)
        a_new[0, 2] *= scale_x
        a_new[1, 2] *= scale_y
        affines_scaled.append(a_new)

    frames_hires: List[np.ndarray] = []
    for i, f in enumerate(frames):
        if i in hires_imgs:
            frames_hires.append(hires_imgs[i])
        else:
            frames_hires.append(
                cv2.resize(f, (hires_w, hires_h), interpolation=cv2.INTER_LANCZOS4)
            )

    masks_resized: List[Optional[np.ndarray]] = []
    for m in bg_masks:
        if m is None:
            masks_resized.append(None)
        else:
            masks_resized.append(
                cv2.resize(m, (hires_w, hires_h), interpolation=cv2.INTER_NEAREST)
            )

    return len(hires_imgs), frames_hires, affines_scaled, masks_resized


class AnimeStitchPipeline:
    """
    Multi-stage anime frame stitching pipeline.

    Parameters
    ----------
    use_basic    : enable BaSiC photometric correction (broadcast dimming removal).
    use_birefnet : enable BiRefNet foreground masking (character exclusion).
    use_loftr    : enable LoFTR dense matching (falls back to template match if False).
    use_ecc      : enable ECC sub-pixel refinement after bundle adjustment.
    renderer     : 'median' — temporal Overmix-style median (suppresses noise);
                   'first'  — always use the first valid frame per canvas pixel;
                   'blend'  — sequential Laplacian blend (nearest to SCANS mode).
    composite_fg : paste the foreground character from the best single frame back
                   onto the median background.
    laplacian_bands : pyramid depth for multi-band blending.
    """

    def __init__(
        self,
        use_basic: bool = True,
        use_birefnet: bool = True,
        use_loftr: bool = True,
        use_efficient_loftr: bool = True,
        use_aliked: bool = True,
        use_roma: bool = True,
        use_sea_raft: bool = True,
        use_ecc: bool = True,
        renderer: str = "median",  # 'median' | 'first' | 'blend'
        composite_fg: bool = True,
        laplacian_bands: int = LAPLACIAN_BANDS,
        edge_crop: int = 30,
        motion_model: str = "translation",  # 'translation' or 'affine' (4-DOF)
        **kwargs,
    ):
        self.kwargs = kwargs
        self.use_basic = use_basic and _BASIC_OK
        self.use_birefnet = use_birefnet and _BIREFNET_OK
        self.use_loftr = use_loftr and _LOFTR_OK
        self.use_efficient_loftr = use_efficient_loftr and _ELOFTR_OK
        self.use_aliked = use_aliked and _ALIKED_OK
        self.use_roma = use_roma and _ROMA_OK
        self.use_sea_raft = use_sea_raft and _SEA_RAFT_OK
        self.use_jamma = kwargs.get("use_jamma", False)
        self.use_ecc = use_ecc
        self.renderer = renderer
        self.composite_fg = composite_fg
        self.bands = laplacian_bands
        self.edge_crop = edge_crop
        self.motion_model = motion_model

        # §1.5D: seam path cache shared across run() invocations on the same frame set
        self._seam_path_cache: Dict = {}

        # Issue 10A3: NL seam routing exclusion masks — set externally before run()
        # List of per-frame uint8 (H,W) masks where >127 forces seam cost=1e6.
        self.exclusion_masks: Optional[List[np.ndarray]] = None

        # Issue 10A2 S83: live SAM-2 predictor state preserved across HITL boundary.
        # Populated by _compute_fg_masks() when _USE_SAM2 is True; freed by
        # _cleanup_sam2_state() after checkpoint 1.5 mask review completes.
        self._sam2_predictor = None
        self._sam2_inference_state = None
        self._sam2_tmp_dir: Optional[str] = None
        self._sam2_frame_h: int = 0
        self._sam2_frame_w: int = 0

        # Lazy-loaded model instances (only allocated if the flag is True)
        self._basic: Optional["BaSiCWrapper"] = None
        self._baselines: Optional[List[float]] = None
        self._birefnet: Optional["BiRefNetWrapper"] = None
        self._loftr: Optional["LoFTRWrapper"] = None
        self._eloftr: Optional["EfficientLoFTRWrapper"] = None
        self._aliked: Optional["ALIKEDLightGlueWrapper"] = None
        self._roma: Optional["RoMaWrapper"] = None
        self._sea_raft = None
        self._stitch_net: Optional["AnimeStitchNet"] = None

    # -------------------------------------------------------------- edge filter

    def _filter_edges(  # noqa: C901
        self,
        edges: List[Dict],
        image_paths: List[str],
        H: int,
        W: int,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[Dict]:
        """
        Apply geometric-consistency + direction-consensus filters to raw edges.

        Separated from ``run()`` so the progress-aware subclass can call it
        after its overridden ``_pairwise_match``.
        """

        # ── §1.2A+C: Pre-filter static edges (adaptive threshold) ───────────
        # §1.2C: derive content-adaptive threshold before §1.2A rejection so
        # that high-resolution / fast-scroll sequences apply a proportionally
        # higher floor (10 % of median adjacent step, min STATIC_EDGE_MIN_DISP_PX).
        _min_disp = _compute_adaptive_min_disp(edges)
        edges = _reject_static_edges(edges, min_disp_px=_min_disp)

        # ── §2.14 + Geometric Consistency + Min-step (batch or Python) ──────
        # C++ batch.matching.filter_edge_graph covers all three classical gates
        # in a single pass; Python fallbacks run individually when batch is absent.
        _batch_filter_ok = False
        if _HAS_BATCH and hasattr(_batch, "matching"):
            try:
                edges = list(
                    _batch.matching.filter_edge_graph(
                        edges,
                        float(MIN_EXPECTED_STEP),
                        15.0,
                        0.0,
                    )
                )
                _batch_filter_ok = True
            except Exception:
                pass

        if not _batch_filter_ok:

            # ── Geometric Consistency Filter ──────────────────────────────────
            if len(edges) > 0:
                adj_map: Dict[int, Tuple[float, float]] = {}
                for e in edges:
                    if e["j"] == e["i"] + 1:
                        adj_map[e["i"]] = (e["M"][0, 2], e["M"][1, 2])

                filtered: List[Dict] = []
                for e in edges:
                    i, j = e["i"], e["j"]
                    if j == i + 1:
                        filtered.append(e)
                        continue
                    can_verify = True
                    sum_dx, sum_dy = 0.0, 0.0
                    for k in range(i, j):
                        if k in adj_map:
                            sum_dx += adj_map[k][0]
                            sum_dy += adj_map[k][1]
                        else:
                            can_verify = False
                            break
                    if can_verify:
                        diff_x = abs(e["M"][0, 2] - sum_dx)
                        diff_y = abs(e["M"][1, 2] - sum_dy)
                        if diff_x < 15.0 and diff_y < 15.0:
                            filtered.append(e)
                        else:
                            logger.debug(
                                f"[Stitch]   Edge {i}→{j} rejected: inconsistency "
                                f"(dx={diff_x:.1f}, dy={diff_y:.1f})"
                            )
                    else:
                        filtered.append(e)
                edges = filtered

            # ── Min-step guard ─────────────────────────────────────────────────
            # Reject adjacent edges with near-zero displacement BEFORE the direction
            # consensus filter so the consensus median is not pulled toward zero.
            if len(edges) >= 3:
                adj_edges = [e for e in edges if e["j"] == e["i"] + 1]
                if len(adj_edges) > 0:
                    median_dx_abs = float(np.median([abs(e["M"][0, 2]) for e in adj_edges]))
                    median_dy_abs = float(np.median([abs(e["M"][1, 2]) for e in adj_edges]))
                    primary_axis = 0 if median_dx_abs > median_dy_abs else 1

                    adj_before = len(adj_edges)
                    edges = [
                        e
                        for e in edges
                        if e["j"] != e["i"] + 1
                        or abs(float(e["M"][primary_axis, 2])) >= MIN_EXPECTED_STEP
                    ]
                    adj_after = sum(1 for e in edges if e["j"] == e["i"] + 1)
                    n_rejected = adj_before - adj_after
                    if n_rejected > 0:
                        logger.debug(
                            f"[Stitch]   Min-step guard: rejected {n_rejected} near-zero "
                            f"edges (threshold={MIN_EXPECTED_STEP}px on axis {primary_axis})"
                        )

        # ── Direction Consensus Filter ────────────────────────────────────────
        if len(edges) >= 3:
            adj_edges = [e for e in edges if e["j"] == e["i"] + 1]
            if len(adj_edges) >= 3:
                median_dx_abs = float(np.median([abs(e["M"][0, 2]) for e in adj_edges]))
                median_dy_abs = float(np.median([abs(e["M"][1, 2]) for e in adj_edges]))
                primary_axis = 0 if median_dx_abs > median_dy_abs else 1

                adj_vals = [e["M"][primary_axis, 2] for e in adj_edges]
                median_val = float(np.median(adj_vals))
                consensus_sign = int(np.sign(median_val))

                # Drop skip edges (j > i+1) that scroll the wrong direction or are noise
                if consensus_sign != 0:
                    _pre_skip_n = len(edges)
                    edges = [
                        e
                        for e in edges
                        if e["j"] == e["i"] + 1
                        or abs(float(e["M"][primary_axis, 2])) < 20.0
                        or int(np.sign(float(e["M"][primary_axis, 2])))
                        == consensus_sign
                    ]
                    _n_skip_dropped = _pre_skip_n - len(edges)
                    if _n_skip_dropped:
                        logger.debug(
                            f"[Stitch]   Skip-edge sign filter: dropped "
                            f"{_n_skip_dropped} wrong-sign skip edges"
                        )

                _ts_pat = re.compile(r"_(\d+)ms", re.IGNORECASE)
                timestamps_ms: List[Optional[int]] = []
                for p in image_paths:
                    m = _ts_pat.search(os.path.basename(p))
                    timestamps_ms.append(int(m.group(1)) if m else None)

                def _interval_ms(fi: int, fj: int) -> Optional[int]:
                    t_i = timestamps_ms[fi] if fi < len(timestamps_ms) else None
                    t_j = timestamps_ms[fj] if fj < len(timestamps_ms) else None
                    if t_i is not None and t_j is not None and t_j != t_i:
                        return abs(t_j - t_i)
                    return None

                def _wrong_sign(val: float) -> bool:
                    return (
                        consensus_sign != 0
                        and np.sign(val) != 0
                        and int(np.sign(val)) != consensus_sign
                    )

                def _gross_outlier(val: float) -> bool:
                    return (
                        abs(val) > 2.0 * abs(median_val)
                        and abs(val - median_val) > 200.0
                    )

                vel_samples = []
                for e in edges:
                    if e["j"] != e["i"] + 1:
                        continue
                    v_e = float(e["M"][primary_axis, 2])
                    if _wrong_sign(v_e) or _gross_outlier(v_e):
                        continue
                    iv = _interval_ms(e["i"], e["j"])
                    if iv is not None:
                        vel_samples.append(v_e / iv)
                vel_px_per_ms: Optional[float] = (
                    float(np.median(vel_samples)) if vel_samples else None
                )
                if vel_px_per_ms is not None:
                    logger.debug(
                        f"[Stitch]   Scroll velocity: {vel_px_per_ms:.4f} px/ms "
                        f"(from {len(vel_samples)} reliable edges)"
                    )

                def _is_outlier(val: float, fi: int, fj: int) -> Tuple[bool, str]:
                    if _wrong_sign(val):
                        return True, "wrong sign"
                    if _gross_outlier(val):
                        return True, "gross outlier"
                    if vel_px_per_ms is not None:
                        iv = _interval_ms(fi, fj)
                        if iv is not None:
                            expected = abs(vel_px_per_ms) * iv
                            if abs(val - expected * consensus_sign) > max(
                                0.15 * expected, 15.0
                            ):
                                return (
                                    True,
                                    f"velocity outlier (expected {expected * consensus_sign:.1f})",
                                )
                    return False, ""

                def _apply_corrected_M(
                    edge: Dict, new_M: np.ndarray, new_weight: float
                ) -> Dict:
                    new_pts_j = edge["pts_i"] + new_M[:, 2].astype(np.float32)
                    return dict(edge, M=new_M, pts_j=new_pts_j, weight=new_weight)

                ec_h = int(H * MATCH_EDGE_CROP)
                ec_w = int(W * MATCH_EDGE_CROP)
                corrected: List[Dict] = []
                for e in edges:
                    if e["j"] == e["i"] + 1:
                        fi, fj = e["i"], e["j"]
                        val = float(e["M"][primary_axis, 2])
                        outlier, reason = _is_outlier(val, fi, fj)
                        if outlier:
                            iv = _interval_ms(fi, fj)
                            replaced = False
                            if vel_px_per_ms is not None and iv is not None:
                                est_val = vel_px_per_ms * iv
                                logger.debug(
                                    f"[Stitch]   Edge {fi}→{fj}: val={val:.1f} ({reason}); "
                                    f"velocity → val={est_val:.1f}"
                                )
                                M_fix = np.eye(2, 3, dtype=np.float32)
                                M_fix[1 - primary_axis, 2] = e["M"][1 - primary_axis, 2]
                                M_fix[primary_axis, 2] = est_val
                                e = _apply_corrected_M(e, M_fix, 0.55)
                                replaced = True
                            if not replaced and primary_axis == 1:
                                img_i_c = frames[fi][ec_h:-ec_h, ec_w:-ec_w]
                                img_j_c = frames[fj][ec_h:-ec_h, ec_w:-ec_w]
                                m_i_c = (
                                    bg_masks[fi][ec_h:-ec_h, ec_w:-ec_w]
                                    if bg_masks[fi] is not None
                                    else None
                                )
                                M_dir, c_dir = _template_match(
                                    img_i_c,
                                    img_j_c,
                                    m_i_c,
                                    None,
                                    img_i_c.shape[0],
                                    direction_sign=consensus_sign,
                                )
                                if (
                                    M_dir is not None
                                    and int(np.sign(M_dir[1, 2])) == consensus_sign
                                ):
                                    new_val = float(M_dir[1, 2])
                                    logger.debug(
                                        f"[Stitch]   Edge {fi}→{fj}: directed TM → "
                                        f"val={new_val:.1f} conf={c_dir:.3f}"
                                    )
                                    M_new = np.array(
                                        [[1, 0, e["M"][0, 2]], [0, 1, new_val]],
                                        dtype=np.float32,
                                    )
                                    e = _apply_corrected_M(e, M_new, c_dir * 0.7)
                                    replaced = True
                            if not replaced:
                                logger.debug(
                                    f"[Stitch]   Edge {fi}→{fj}: val={val:.1f} ({reason}); "
                                    f"using median {median_val:.1f}"
                                )
                                M_fix = np.eye(2, 3, dtype=np.float32)
                                M_fix[1 - primary_axis, 2] = e["M"][1 - primary_axis, 2]
                                M_fix[primary_axis, 2] = median_val
                                e = _apply_corrected_M(
                                    e, M_fix, e.get("weight", 1.0) * 0.3
                                )
                        else:
                            logger.debug(
                                f"[Stitch]   Edge {fi}→{fj}: val={val:.1f} kept "
                                f"(consensus {median_val:.1f})"
                            )
                    corrected.append(e)
                edges = corrected

        return edges

    # ---------------------------------------------------------------- public

    def run(  # noqa: C901
        self,
        image_paths: List[str],
        output_path: str,
        hires_keyframes: Optional[Dict[int, str]] = None,
    ) -> Image.Image:
        """
        Execute the full stitching pipeline.

        Parameters
        ----------
        image_paths : ordered list of source frame paths (first = leftmost/topmost).
        output_path : destination PNG/WEBP path.
        hires_keyframes : optional mapping of {frame_idx: hires_path} (§9C Sprint 8).
            When provided, all heavy computation runs at proxy (1080p) resolution;
            after Stage 8 (ECC/SEA-RAFT refinement), the selected frames are
            replaced by their hires counterparts and affines are scaled accordingly.
            Frame indices not listed are bicubic-upscaled from the proxy.
            The final panorama is rendered at the hires resolution.

        Returns
        -------
        PIL.Image of the final stitched panorama.
        """
        # Exclude the output file if it was accidentally included in the input list.
        out_abs = os.path.abspath(output_path)
        image_paths = [p for p in image_paths if os.path.abspath(p) != out_abs]

        # §1.63: Sort frame paths by numeric suffix so glob-discovered frames are
        # always in temporal order, regardless of OS directory-entry order.
        image_paths = _sort_frames_by_index(image_paths)

        logger.info(
            f"[Stitch] Starting AnimeStitchPipeline on {len(image_paths)} frames."
        )
        self._baselines = None

        # ── §3.16B: Per-test HITL preset ─────────────────────────────────────
        _test_name = Path(image_paths[0]).parent.name if image_paths else ""
        _hitl_pipeline_state: dict = {}

        # ── Stage 1: Load and trim ─────────────────────────────────────────────
        frames = _load_frames(image_paths)
        N = len(frames)
        if N < 2:
            raise PipelineError("Need at least 2 valid frames to stitch.")
        logger.info(f"[Stitch] Stage 1 complete: {N} frames loaded.")

        # ── Stage 2: Width normalisation ─────────────────────────────────────
        frames = _normalise_widths(frames)
        H, W = frames[0].shape[:2]
        scans_frames = list(frames)
        logger.info(f"[Stitch] Stage 2 complete: all frames at {W}×{H}.")

        # ── Stage 3: BaSiC photometric correction ────────────────────────────
        if self.use_basic:
            if self._basic is None:
                self._basic = BaSiCWrapper()
            frames, baselines = _apply_basic(frames, self._basic)
            self._baselines = baselines
            frames = _correct_vignetting(frames)
            logger.info(
                "[Stitch] Stage 3 complete: BaSiC + Vignette correction applied."
            )
        else:
            logger.info("[Stitch] Stage 3 skipped (use_basic=False).")

        # ── Stage 4: Foreground masking ──────────────────────────────────────
        if self.use_birefnet and self._birefnet is None:
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )  # §3.14 lazy

            self._birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(
            frames,
            self._birefnet,
            use_birefnet=self.use_birefnet,
        )
        if self._birefnet is not None:
            with contextlib.suppress(Exception):
                self._birefnet.unload()
            self._birefnet = None
        logger.debug(
            f"[Stitch] Stage 4 complete: foreground masks ready "
            f"({'BiRefNet' if self.use_birefnet else 'None'})."
        )

        # ── Stage 4.5: Background-based photometric normalisation ────────────
        # Compute the per-frame mean background color (bg_mask > 127) and normalise
        # every frame to the same median background level.  This eliminates
        # frame-to-frame ambient lighting variation (anime cel flicker) which
        # would otherwise appear as horizontal color seams in the temporal median.
        bg_frame_means: List[Optional[np.ndarray]] = []
        for _i, (_frame, _mask) in enumerate(zip(frames, bg_masks, strict=False)):
            if _mask is not None:
                _bg_px = _frame[_mask > 127].astype(np.float32)
                if len(_bg_px) >= 1000:
                    bg_frame_means.append(_bg_px.mean(axis=0))
                    continue
            bg_frame_means.append(None)

        _valid_means = [m for m in bg_frame_means if m is not None]
        if len(_valid_means) >= 3:
            _ref_mean = np.median(_valid_means, axis=0)  # (3,) BGR reference
            for _i in range(N):
                if bg_frame_means[_i] is None:
                    continue
                _gain = _ref_mean / np.maximum(bg_frame_means[_i], 1.0)
                _ref_lum_scalar = float(np.dot(_ref_mean, [0.114, 0.587, 0.299]))
                _gain_lo, _gain_hi = (
                    (0.80, 1.25) if _ref_lum_scalar < 80.0 else (0.88, 1.14)
                )
                _gain = np.clip(_gain, _gain_lo, _gain_hi)
                if not np.allclose(_gain, 1.0, atol=0.01):
                    frames[_i] = np.clip(
                        frames[_i].astype(np.float32) * _gain, 0, 255
                    ).astype(np.uint8)
            logger.debug(
                f"[Stitch] Stage 4.5 complete: background photometric normalisation "
                f"({len(_valid_means)}/{N} frames had sufficient background)."
            )

        # P2.6 — Per-segment photometric correction.
        # The global gain above applies one scalar per frame.  Anime assigns
        # different exposure levels to different colour regions (sky vs costume
        # vs background props), so a single gain is a poor approximation.
        # This pass refines correction at the connected-component level,
        # matching each background segment to the reference (frame 0) segment
        # with the closest colour, removing per-region flicker independently.
        _n_seg_corrected = 0
        for _i in range(1, N):
            if bg_masks[_i] is None:
                continue
            bm = bg_masks[_i] > 127
            if bm.sum() < 1000:
                continue
            # Quick color-region segmentation via quantization (no SAM needed)
            img_small = cv2.resize(
                frames[_i],
                (frames[_i].shape[1] // 4, frames[_i].shape[0] // 4),
                cv2.INTER_AREA,
            )
            flat = img_small.reshape(-1, 3).astype(np.float32)
            _, labels_flat, centers = cv2.kmeans(
                flat,
                min(8, len(np.unique(flat.reshape(-1)))),
                None,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                2,
                cv2.KMEANS_PP_CENTERS,
            )
            seg_map = labels_flat.reshape(img_small.shape[:2])
            seg_map_full = cv2.resize(
                seg_map.astype(np.uint8),
                (frames[_i].shape[1], frames[_i].shape[0]),
                cv2.INTER_NEAREST,
            )
            # Reference: frame 0 colour clusters
            img0_small = cv2.resize(
                frames[0], img_small.shape[:2][::-1], cv2.INTER_AREA
            )
            flat0 = img0_small.reshape(-1, 3).astype(np.float32)
            ref_centers = cv2.kmeans(
                flat0,
                min(8, len(np.unique(flat0.reshape(-1)))),
                None,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
                2,
                cv2.KMEANS_PP_CENTERS,
            )[2]

            gain_map = np.ones(frames[_i].shape[:2], dtype=np.float32)
            for _k in range(int(seg_map_full.max()) + 1):
                _seg_px = (seg_map_full == _k) & bm
                if _seg_px.sum() < 200:
                    continue
                _seg_mean = frames[_i][_seg_px].astype(np.float32).mean(axis=0)  # (3,)
                # Find closest reference cluster by colour distance
                _dists = np.linalg.norm(ref_centers - _seg_mean[np.newaxis], axis=1)
                _ref_seg = ref_centers[int(np.argmin(_dists))]
                _gain_seg = np.clip(_ref_seg / np.maximum(_seg_mean, 1.0), 0.88, 1.12)
                gain_map[_seg_px] = _gain_seg.mean()

            frames[_i] = np.clip(
                frames[_i].astype(np.float32) * gain_map[..., np.newaxis], 0, 255
            ).astype(np.uint8)
            _n_seg_corrected += 1
        if _n_seg_corrected > 0:
            logger.debug(
                f"[Stitch] Stage 4.5b: per-segment photometric correction applied to {_n_seg_corrected} frames."
            )

        # ── Pre-stage 5: Deduplicate near-static consecutive frames ─────────
        if N >= 3:
            _luma_cache = [
                cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames
            ]
            keep = [True] * N
            _prev_kept = 0
            for _fi in range(1, N):
                _la, _lb = _luma_cache[_fi], _luma_cache[_prev_kept]
                if _la.shape != _lb.shape:
                    # Different heights — cannot be duplicates; keep both
                    _prev_kept = _fi
                    continue
                diff = float(np.abs(_la - _lb).mean())
                if diff < NEAR_DUP_LUMA_THRESH:
                    keep[_fi] = False
                    logger.debug(
                        f"[Stitch]   Dedup: frame {_fi} ≈ frame {_prev_kept} "
                        f"(luma_diff={diff:.2f}) — dropped."
                    )
                else:
                    _prev_kept = _fi
            if not all(keep):
                keep_idx = [i for i, k in enumerate(keep) if k]
                frames = [frames[i] for i in keep_idx]
                scans_frames = (
                    [scans_frames[i] for i in keep_idx] if scans_frames else []
                )  # §1.9C
                bg_masks = [bg_masks[i] for i in keep_idx]
                image_paths = [image_paths[i] for i in keep_idx]
                N = len(frames)
                logger.debug(
                    f"[Stitch]   Dedup complete: {sum(not k for k in keep)} "
                    f"removed, {N} remain."
                )
                if N < 2:
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 5-6: Pairwise matching (+ skip-pair edges) ────────────────
        # ── Matcher selection (P1.4 EfficientLoFTR / P3.2 JamMa) ───────────────
        # Priority: JamMa (4K only) → EfficientLoFTR → kornia LoFTR → None.
        _is_4k = H * W > 3000 * 2000
        _active_loftr = None

        if self.use_jamma and _is_4k:
            try:
                from backend.src.models.wrappers.jamma_wrapper import JamMaWrapper  # §3.14 lazy

                _jamma_inst = JamMaWrapper()
                _jamma_inst.load_model()
                _active_loftr = _jamma_inst
                logger.info(f"[Stitch]   4K frame ({W}×{H}): using JamMa (O(N) Mamba).")
            except Exception as _jm_e:
                logger.info(
                    f"[Stitch]   JamMa unavailable ({_jm_e}); using EfficientLoFTR."
                )

        # P1.4 — Use EfficientLoFTR (2.5× faster) when available; fall back to
        # kornia LoFTR.  Both expose the same .match() interface.
        if _active_loftr is None and self.use_efficient_loftr:
            if self._eloftr is None:
                try:
                    from backend.src.models.wrappers.efficient_loftr_wrapper import (
                        EfficientLoFTRWrapper,
                    )  # §3.14 lazy

                    self._eloftr = EfficientLoFTRWrapper()
                    self._eloftr.load_model()
                    _active_loftr = self._eloftr
                    logger.info(
                        "[Stitch]   Using EfficientLoFTR (2.5× faster than LoFTR)."
                    )
                except Exception as _e:
                    logger.debug(
                        f"[Stitch]   EfficientLoFTR init failed ({_e}); falling back to LoFTR."
                    )
                    self.use_efficient_loftr = False
                    self._eloftr = None
            else:
                self._eloftr.load_model()
                _active_loftr = self._eloftr
        if _active_loftr is None and self.use_loftr:
            if self._loftr is None:
                from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper  # §3.14 lazy

                self._loftr = LoFTRWrapper()
            _active_loftr = self._loftr

        if self.use_aliked and self._aliked is None:
            try:
                from backend.src.models.wrappers.aliked_lg_wrapper import (
                    ALIKEDLightGlueWrapper,
                )  # §3.14 lazy

                self._aliked = ALIKEDLightGlueWrapper()
            except Exception as _e:
                logger.info(
                    f"[Stitch]   ALIKED+LightGlue init failed ({_e}); disabling."
                )
                self.use_aliked = False
                self._aliked = None
        if self.use_roma and self._roma is None:
            try:
                self._roma = RoMaWrapper()
            except Exception as _e:
                logger.info(f"[Stitch]   RoMa init failed ({_e}); disabling.")
                self.use_roma = False
                self._roma = None
        edges = _pairwise_match(
            frames,
            bg_masks,
            loftr_wrapper=_active_loftr,
            use_loftr=_active_loftr is not None,
            motion_model=self.motion_model,
            aliked_wrapper=self._aliked if self.use_aliked else None,
            roma_wrapper=self._roma if self.use_roma else None,
        )

        # ── Post-match: Spatial dedup of near-static consecutive frames ──────
        # Frames whose measured adj displacement is < SPATIAL_DEDUP_PX add no
        # meaningful new content and confuse BA (effective gap ≈ 0).  Run in a
        # loop so chains (A≈B≈C) are resolved in successive passes after
        # re-indexing turns a former skip-edge into an adj-edge.

        _total_spa_dropped = 0
        _spa_changed = True
        while _spa_changed:
            frames, scans_frames, bg_masks, image_paths, edges, _n_dropped = (
                _spatial_dedup_frames(
                    frames,
                    scans_frames,
                    bg_masks,
                    image_paths,
                    edges,
                    SPATIAL_DEDUP_PX,
                )
            )
            _spa_changed = _n_dropped > 0
            if _n_dropped:
                _total_spa_dropped += _n_dropped
                logger.debug(
                    f"[Stitch]   Spatial dedup pass: {_n_dropped} frame(s) dropped, "
                    f"{len(frames)} remain."
                )
                N = len(frames)
                if N < 2:
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _scan_stitch_fallback(_sf, output_path)
        if _total_spa_dropped:
            logger.debug(
                f"[Stitch]   Spatial dedup complete: {_total_spa_dropped} frames "
                f"removed, {N} remain."
            )

        edges = self._filter_edges(edges, image_paths, H, W, frames, bg_masks)

        # §3.16B: apply HITL drop_edges after filter
        if _hitl_pipeline_state.get("boundaries"):
            logger.info(
                f"[Stitch] §3.16B: HITL preset '{_test_name}' — "
                f"forced_boundaries={_hitl_pipeline_state['boundaries']}."
            )

        for _mdl in [self._loftr, self._eloftr, self._aliked, self._roma]:
            if _mdl is not None:
                try:
                    _mdl.unload()
                except Exception:
                    with contextlib.suppress(Exception):
                        _mdl.offload()
        self._loftr = None
        self._eloftr = None
        self._aliked = None
        self._roma = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        logger.info(f"[Stitch] Stages 5-6 complete: {len(edges)} valid edges found.")
        if not edges:
            warnings.warn("[Stitch] No valid edges — falling back to scan stitch.", stacklevel=2)
            _sf = scans_frames or _reload_scans_frames(image_paths)
            return _scan_stitch_fallback(_sf, output_path)

        # ── §1.15: Edge graph connectivity gate ───────────────────────────────
        # A disconnected edge graph means BA will assign wrong translations to
        # isolated frames.  Detect and fall back to SCANS before the bad solve.
        if not _check_edge_graph_connectivity(edges, N):
            logger.info(
                "[Stitch] §1.15: Edge graph is disconnected (%d edges, %d frames) "
                "→ SCANS fallback.",
                len(edges),
                N,
            )
            _sf = scans_frames or _reload_scans_frames(image_paths)
            return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 7: Global bundle adjustment ────────────────────────────────
        use_affine_ba = getattr(self, "motion_model", "affine") == "affine"
        affines = _bundle_adjust_affine(edges, N, use_affine=use_affine_ba)
        logger.debug(
            f"[Stitch] Stage 7 complete: bundle adjustment done "
            f"(mode={'affine' if use_affine_ba else 'translation'})."
        )

        # ── Stage 7b: Affine validation gate ─────────────────────────────────
        # §0.5C: adaptive min_gap — scales with canvas span so fast-scroll
        # (4K, >400 px/frame) applies a proportionally higher floor than the
        # fixed 25 px default, while slow-scroll sequences use 20 px.
        _adaptive_min_gap = _compute_adaptive_min_gap(affines)
        _adaptive_rot, _adaptive_sc = _compute_adaptive_rot_scale(affines)
        health = _validate_affines(
            affines,
            min_step=_adaptive_min_gap,
            max_rotation=_adaptive_rot,
            max_scale_dev=_adaptive_sc,
        )
        logger.debug(
            f"[Stitch]   Affine health: valid={health.valid}, "
            f"ratio={health.ratio:.1f}×, min_gap={health.min_gap:.0f}px "
            f"(adaptive_floor={_adaptive_min_gap:.1f}px), "
            f"max_rot={health.max_rotation:.4f} (thresh={_adaptive_rot:.2f}), "
            f"scale_dev={health.max_scale_dev:.4f} (thresh={_adaptive_sc:.2f})"
        )
        if not health.valid:
            logger.debug(
                f"[Stitch]   Affine health FAILED ({health.reason}); attempting recovery..."
            )
            # Retry 0: §2.9C — high-confidence-only re-solve (ratio failures only).
            # Low-confidence TM/PC fallback edges (weight 0.15–0.55) can corrupt BA
            # when a single bad edge pulls two frames together → inflated ratio.
            # Filter to LoFTR-quality edges (weight ≥ HIGH_CONF_EDGE_THRESH) and
            # re-solve if enough survive.  Falls through to Retry 1 if not.
            if health.reason.startswith("ratio="):
                _hc_edges = _filter_high_conf_edges(edges)
                if len(_hc_edges) >= N - 1:
                    _affines_r0 = _bundle_adjust_affine(
                        _hc_edges, N, use_affine=use_affine_ba
                    )
                    _health_r0 = _validate_affines(
                        _affines_r0,
                        min_step=_adaptive_min_gap,
                        max_rotation=_adaptive_rot,
                        max_scale_dev=_adaptive_sc,
                    )
                    logger.debug(
                        f"[Stitch]   Retry 0 (high-conf edges, {len(_hc_edges)} edges): "
                        f"valid={_health_r0.valid}, {_health_r0.reason}"
                    )
                    if _health_r0.valid:
                        affines, health = _affines_r0, _health_r0

            # Retry 1: consecutive-only bundle — skip edges sometimes corrupt the solution
            _adj_only = [e for e in edges if e["j"] == e["i"] + 1]
            if len(_adj_only) >= N - 1:
                affines_r1 = _bundle_adjust_affine(
                    _adj_only, N, use_affine=use_affine_ba
                )
                health_r1 = _validate_affines(affines_r1)
                logger.debug(
                    f"[Stitch]   Retry 1 (adj-only bundle): "
                    f"valid={health_r1.valid}, {health_r1.reason}"
                )
                if health_r1.valid:
                    affines, health = affines_r1, health_r1
            # Retry 2: smart sequential integration with gap-filling
            if not health.valid:
                _adj_only_r2 = [e for e in edges if e["j"] == e["i"] + 1]
                # Consensus step for interpolation/extrapolation of isolated frames
                _step_dx = (
                    float(np.median([float(e["M"][0, 2]) for e in _adj_only_r2]))
                    if _adj_only_r2
                    else 0.0
                )
                _step_dy = (
                    float(np.median([float(e["M"][1, 2]) for e in _adj_only_r2]))
                    if _adj_only_r2
                    else 0.0
                )
                # Frames that have an adj edge pointing to them
                _has_adj_src = {e["j"] for e in _adj_only_r2}

                _seq = [np.eye(2, 3, dtype=np.float32) for _ in range(N)]
                _anchored: set = {0}

                # Pass 1: greedy — for each frame use the shortest-span edge from an anchored frame
                for _f in range(1, N):
                    _best_e, _best_span = None, float("inf")
                    for _e in edges:
                        if _e["j"] == _f and _e["i"] in _anchored and _f - _e["i"] < _best_span:
                            _best_span = _f - _e["i"]
                            _best_e = _e
                    if _best_e is not None:
                        _seq[_f][0, 2] = _seq[_best_e["i"]][0, 2] - float(
                            _best_e["M"][0, 2]
                        )
                        _seq[_f][1, 2] = _seq[_best_e["i"]][1, 2] - float(
                            _best_e["M"][1, 2]
                        )
                        _anchored.add(_f)

                # Pass 2: fill frames with no adj edge via interpolation or velocity extrapolation
                for _uf in sorted(i for i in range(N) if i not in _anchored):
                    if _uf in _has_adj_src:
                        continue  # will be chained in Pass 3
                    _lft = max((a for a in _anchored if a < _uf), default=None)
                    _rgt = min((a for a in _anchored if a > _uf), default=None)
                    if _lft is not None and _rgt is not None:
                        _t = (_uf - _lft) / (_rgt - _lft)
                        _seq[_uf][0, 2] = (
                            _seq[_lft][0, 2] * (1 - _t) + _seq[_rgt][0, 2] * _t
                        )
                        _seq[_uf][1, 2] = (
                            _seq[_lft][1, 2] * (1 - _t) + _seq[_rgt][1, 2] * _t
                        )
                    elif _lft is not None:
                        _n = _uf - _lft
                        _seq[_uf][0, 2] = _seq[_lft][0, 2] - _n * _step_dx
                        _seq[_uf][1, 2] = _seq[_lft][1, 2] - _n * _step_dy
                    _anchored.add(_uf)

                # Pass 3: propagate through adj/skip edges from newly-anchored gap frames
                _chg = True
                while _chg:
                    _chg = False
                    for _f in range(1, N):
                        if _f in _anchored:
                            continue
                        _best_e, _best_span = None, float("inf")
                        for _e in edges:
                            if _e["j"] == _f and _e["i"] in _anchored and _f - _e["i"] < _best_span:
                                _best_span = _f - _e["i"]
                                _best_e = _e
                        if _best_e is not None:
                            _seq[_f][0, 2] = _seq[_best_e["i"]][0, 2] - float(
                                _best_e["M"][0, 2]
                            )
                            _seq[_f][1, 2] = _seq[_best_e["i"]][1, 2] - float(
                                _best_e["M"][1, 2]
                            )
                            _anchored.add(_f)
                            _chg = True

                health_r2 = _validate_affines(_seq)
                logger.debug(
                    f"[Stitch]   Retry 2 (sequential+fill): "
                    f"valid={health_r2.valid}, {health_r2.reason}"
                )
                if health_r2.valid:
                    affines, health = _seq, health_r2
                else:
                    # Retry 3: accept with relaxed min_gap when ratio is still healthy
                    health_r3 = _validate_affines(_seq, min_step=20.0)
                    if health_r3.valid:
                        logger.debug(
                            f"[Stitch]   Retry 3 (relaxed min_gap=20px): "
                            f"valid={health_r3.valid}, {health_r3.reason}"
                        )
                        affines, health = _seq, health_r3
            if not health.valid:
                # §1.3B: PANORAMA stitcher handles scale/rotation that
                # translation-only validation rejects; try before SCANS.
                try:
                    _sf = scans_frames or _reload_scans_frames(image_paths)
                    return _panorama_stitch_fallback(_sf, output_path)
                except Exception as _pano_e:
                    logger.info(
                        f"[Stitch]   PANORAMA fallback failed ({_pano_e}); using SCANS."
                    )
                warnings.warn(
                    f"[Stitch] Affine validation FAILED ({health.reason}) after retries. "
                    f"Falling back to SCANS stitch.", stacklevel=2
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # ── Stage 8: Sub-pixel refinement ────────────────────────────────────
        # P2.1 — SEA-RAFT replaces ECC when available.  ECC fails on flat anime
        # cells (near-zero gradients → singular Hessian).  SEA-RAFT uses learned
        # cost volumes that remain informative over uniform colour regions.
        if self.use_sea_raft:
            try:
                if self._sea_raft is None:
                    _dev = "cuda" if torch.cuda.is_available() else "cpu"
                    self._sea_raft = _load_sea_raft(device=_dev)
                    logger.info("[Stitch]   SEA-RAFT model loaded.")
                affines = _flow_refine(
                    frames,
                    affines,
                    bg_masks,
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    raft_model=self._sea_raft,
                )
                logger.info("[Stitch] Stage 8 complete: SEA-RAFT flow refinement done.")
                # Offload SEA-RAFT after use
                if torch.cuda.is_available():
                    with contextlib.suppress(Exception):
                        self._sea_raft.cpu()
                    torch.cuda.empty_cache()
                    self._sea_raft = None
            except Exception as _ecc_e:
                logger.info(
                    f"[Stitch]   SEA-RAFT failed ({_ecc_e}); falling back to ECC."
                )
                if self.use_ecc:
                    affines = _ecc_refine(frames, affines, bg_masks)
                    logger.info(
                        "[Stitch] Stage 8 complete: ECC refinement done (fallback)."
                    )
        elif self.use_ecc:
            affines = _ecc_refine(frames, affines, bg_masks)
            logger.info("[Stitch] Stage 8 complete: ECC refinement done.")
        else:
            logger.info("[Stitch] Stage 8 skipped (use_ecc=False, use_sea_raft=False).")

        # ── Stage 8.8: Hires keyframe substitution (§9C — Sprint 8) ────────
        # All heavy computation above ran on proxy (1080p) frames. If the caller
        # provided hires_keyframes, swap in the full-resolution images now and
        # scale the locked affines so Stage 9 (canvas) operates at hires resolution.
        if hires_keyframes:
            _n_hires, frames, affines, bg_masks = _apply_hires_keyframes(
                frames, affines, bg_masks, hires_keyframes
            )
            if _n_hires > 0:
                logger.info(
                    f"[Stitch] Stage 8.8: substituted {_n_hires} hires frame(s); "
                    f"canvas will render at {frames[0].shape[1]}×{frames[0].shape[0]} px."
                )
            else:
                logger.warning(
                    "[Stitch] Stage 8.8: hires_keyframes provided but no valid paths "
                    "could be loaded — continuing at proxy resolution."
                )

        # ── Stage 9: Canvas construction ────────────────────────────────────
        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        logger.info(f"[Stitch] Stage 9: canvas size {canvas_w}×{canvas_h}.")
        if canvas_h <= 0 or canvas_w <= 0:
            raise CanvasError("Computed canvas has zero size.")

        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        # P1.9 — Bidirectional midplane projection (StabStitch++).
        # Centres the affine coordinate system on the temporal midplane rather
        # than anchoring everything to frame 0.  For long pans (e.g. 14 frames,
        # 150px/step) this halves the maximum per-frame distortion distance,
        # reducing warp artefacts symmetrically across the sequence.
        T_mid_x = float(np.mean([a[0, 2] for a in affines]))
        T_mid_y = float(np.mean([a[1, 2] for a in affines]))
        for i in range(N):
            affines[i][0, 2] -= T_mid_x
            affines[i][1, 2] -= T_mid_y
        # Recompute canvas after midplane shift so T_global absorbs the offset.
        canvas_h, canvas_w, T_global2 = _compute_canvas(frames, affines)
        for i in range(N):
            affines[i][0, 2] += T_global2[0]
            affines[i][1, 2] += T_global2[1]
        logger.debug(
            f"[Stitch] Stage 9 complete: midplane shift ({T_mid_x:.1f}, {T_mid_y:.1f}), "
            f"canvas {canvas_w}×{canvas_h}."
        )

        # §3.14 — Scroll axis classification (logged; horizontal → SCANS fallback).
        # Compositing assumes vertical strips; horizontal scroll produces garbled output
        # without a full horizontal-strip compositing mode (not yet implemented).
        scroll_axis = _detect_scroll_axis(affines)
        logger.info(f"[Stitch] Stage 9.5: scroll axis = '{scroll_axis}'.")
        if scroll_axis == "horizontal":
            logger.info(
                "[Stitch] Horizontal scroll (tx_range >> ty_range) — vertical-strip "
                "compositing not applicable; falling back to SCANS."
            )
            return _scan_stitch_fallback(scans_frames, output_path)

        # ── §4.7: dy_cv pre-detection gate ───────────────────────────────────
        # When step-size CV is high the scroll is too irregular for ARAP/seam
        # compositing — SCANS trivially handles these sequences.
        if _DY_CV_MAX > 0.0:
            _dy_cv_gate = _compute_dy_cv(affines)
            _dy_cv_adaptive_max = _compute_adaptive_dy_cv_max(N, _DY_CV_MAX)
            if _dy_cv_gate >= _dy_cv_adaptive_max:
                logger.info(
                    "[Stitch] §4.7/§5.8: dy_cv=%.3f ≥ %.2f (irregular scroll, N=%d) "
                    "→ SCANS fallback (ASP seam routing degrades severely at high dy_cv).",
                    _dy_cv_gate,
                    _dy_cv_adaptive_max,
                    N,
                )
                _sf = scans_frames or _reload_scans_frames(image_paths)
                return _scan_stitch_fallback(_sf, output_path)

        # P1.3 — Compute per-frame matching confidence for weighted median (W3).
        # Each frame's confidence = the maximum edge weight of its adjacent edges.
        # LoFTR edges have weight ~0.9; TM/PC fallbacks have 0.15–0.55.
        # Frame 0 is always the anchor (confidence 1.0 by convention).
        _frame_confs = np.ones(N, dtype=np.float32)
        for _e in edges:
            _fi, _fj, _w = _e["i"], _e["j"], float(_e.get("weight", 1.0))
            if _e["j"] == _e["i"] + 1:  # only adjacent edges for per-frame confidence
                _frame_confs[_fi] = max(_frame_confs[_fi], _w)
                _frame_confs[_fj] = max(_frame_confs[_fj], _w)
        _frame_confs = np.clip(_frame_confs, 0.0, 1.0)

        # ── Stage 9.5: Alignment stability gate ─────────────────────────────
        # Log severe 2D motion but only abort at a very high threshold — the
        # render gate (in the calling benchmark) uses a SCANS-relative comparison
        # and catches genuinely degraded composites regardless of motion pattern.
        # Hard-abort threshold raised to 200px (was 50px); scenes with horizontal
        # drift up to ~2 frame-widths can still produce acceptable composites.
        # Override: ASP_ALIGN_GATE_DX env var (default 200; set to 50 to restore
        # the old strict behaviour; set to 9999 to disable entirely).
        try:
            _align_dx_limit = float(os.environ.get("ASP_ALIGN_GATE_DX", "200"))
        except ValueError:
            _align_dx_limit = 200.0
        _txs_gate = [float(affines[i][0, 2]) for i in range(N)]
        _dx_gate = [abs(_txs_gate[i + 1] - _txs_gate[i]) for i in range(N - 1)]
        if _dx_gate:
            _dx_p75 = float(np.percentile(_dx_gate, 75))
            if _dx_p75 > _align_dx_limit:
                logger.info(
                    f"[Stitch] Alignment stability gate: 75th-pct |dx|={_dx_p75:.1f}px "
                    f"> {_align_dx_limit:.0f}px limit — extreme 2D motion, "
                    f"falling back to SCANS."
                )
                return _scan_stitch_fallback(scans_frames, output_path)

        # ── Stage 10: Temporal renderer ─────────────────────────────────────
        # P1.2 — Variable-step renderer switch (W2 fix for test16).
        # When step-size variance is high (dy_cv > 0.20), the temporal median
        # blurs in proportion to overlap inconsistency across frames.  Switching
        # to 'first' (first-frame-wins per canvas pixel) avoids cross-frame
        # averaging at boundary zones and matches what SCANS naturally produces.
        effective_renderer = self.renderer
        if self.renderer == "median" and N >= 3:
            _dy_steps = [
                abs(float(affines[k][1, 2]) - float(affines[k - 1][1, 2]))
                for k in range(1, N)
            ]
            _mean_dy = float(np.mean(_dy_steps)) if _dy_steps else 1.0
            _dy_cv = float(np.std(_dy_steps)) / max(_mean_dy, 1.0) if _dy_steps else 0.0
            if _dy_cv > 0.20:
                effective_renderer = "first"
                logger.debug(
                    f"[Stitch]   High step variance (dy_cv={_dy_cv:.3f} > 0.20) — "
                    f"switching renderer to 'first'."
                )

        canvas, valid_mask, warped_corr, warped_fgs = _render(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            renderer=effective_renderer,
            baselines=self._baselines,
            confidence_weights=_frame_confs,
        )
        logger.info("[Stitch] Stage 10 complete: temporal render done.")

        # ── Stage 10.5: Multi-frame canvas coverage gate (§0 item 2) ─────────
        # For each canvas row count how many frames contribute content.
        # If < ASP_COV_MIN_MULTI_PCT (default 30%) of content rows have ≥2-frame
        # coverage, the temporal median is effectively "first-frame-wins" across
        # the entire canvas — it cannot suppress animation ghosting.  Composite
        # on such a canvas would amplify ghosting rather than remove it.
        # Conservative default (30%) avoids false positives while catching truly
        # degenerate selections (e.g., 2 widely-spaced frames in a tall canvas).
        _row_cov, _pct_cov_multi, _cov_median = _compute_row_coverage(
            affines, frames, canvas_h
        )
        _n_cov_total = int((_row_cov > 0).sum())
        _n_cov_multi = (
            int((_row_cov[_row_cov > 0] >= 2).sum()) if _n_cov_total > 0 else 0
        )
        logger.info(
            f"[Stitch] Stage 10.5: coverage — "
            f"{_n_cov_multi}/{_n_cov_total} rows ({_pct_cov_multi:.0%}) "
            f"have ≥2-frame coverage; median={_cov_median:.1f}"
        )
        if _n_cov_total > 0:
            try:
                _cov_min_pct = float(os.environ.get("ASP_COV_MIN_MULTI_PCT", "0.30"))
            except ValueError:
                _cov_min_pct = 0.30
            if _pct_cov_multi < _cov_min_pct:
                logger.info(
                    f"[Stitch] Stage 10.5: coverage gate — {_pct_cov_multi:.0%} < "
                    f"{_cov_min_pct:.0%} threshold, temporal median insufficient "
                    f"for deghosting → SCANS fallback."
                )
                return _scan_stitch_fallback(scans_frames, output_path)

        # ── Stage 11: Foreground composite ──────────────────────────────────
        if self.composite_fg and self.use_birefnet:
            canvas = _composite_foreground(
                [],
                [],
                canvas,
                canvas_h,
                canvas_w,
                frames,
                affines,
                bg_masks,
                frame_keys=tuple(image_paths),
                seam_path_cache=self._seam_path_cache,
                exclusion_masks=self.exclusion_masks or None,
            )
            logger.info("[Stitch] Stage 11 complete: foreground composited.")

        # ── Stage 12: Remaining seam blend (handled inside _render). ────────

        # ── Stage 12.5: Scroll-axis-aware content crop (§2.6) ───────────────
        # After compositing, the canvas may have leading/trailing strips of
        # pure background that contain zero foreground character pixels across
        # all frames.  These pure-bg rows inflate the scale factor relative to
        # GT (GT's panorama starts/ends with the first/last character-containing
        # frame).  Trim them to reduce GT-framing bias.
        #
        # Only trim rows where ALL warped frames have bg-only content (i.e., no
        # character pixels from any frame reach that canvas row).  Rows where
        # even one frame has fg content are kept — they contain mid-scroll
        # character data even if the median/composite shows bg there.
        #
        # Cap: never trim more than 15% of canvas height/width per side.
        # This prevents over-cropping on datasets where the first/last frame
        # is entirely background (static camera opening shot).
        try:
            _trim_cap_frac = 0.15
            # Determine dominant scroll axis from affine translations
            _tys_trim = [float(affines[k][1, 2]) for k in range(N)]
            _txs_trim = [float(affines[k][0, 2]) for k in range(N)]
            _ty_span = max(_tys_trim) - min(_tys_trim)
            _tx_span = max(_txs_trim) - min(_txs_trim)
            _is_vert_scroll = _ty_span >= _tx_span

            if bg_masks and any(m is not None for m in bg_masks):
                # Build a union fg map across all warped frames:
                # any pixel that is foreground in AT LEAST ONE warped frame
                # is protected from trimming.
                _union_fg = np.zeros((canvas_h, canvas_w), dtype=bool)
                for _idx_trim in range(N):
                    if bg_masks[_idx_trim] is None:
                        continue
                    _wfg = cv2.warpAffine(
                        (bg_masks[_idx_trim] < 127).astype(np.uint8),
                        affines[_idx_trim],
                        (canvas_w, canvas_h),
                        flags=cv2.INTER_NEAREST,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                    _union_fg |= _wfg > 0

                if _is_vert_scroll:
                    # Find row range with any fg content
                    _row_has_fg = _union_fg.any(axis=1)  # (canvas_h,)
                    _fg_rows = np.where(_row_has_fg)[0]
                    if len(_fg_rows) > 0:
                        _cap_px = int(canvas_h * _trim_cap_frac)
                        _new_top = max(0, min(int(_fg_rows[0]), _cap_px))
                        _new_bot = min(
                            canvas_h, max(int(_fg_rows[-1]) + 1, canvas_h - _cap_px)
                        )
                        if _new_top > 0 or _new_bot < canvas_h:
                            canvas = canvas[_new_top:_new_bot]
                            valid_mask = valid_mask[_new_top:_new_bot]
                            logger.info(
                                f"[Stitch] Stage 12.5: vertical scroll content trim "
                                f"rows [{_new_top}:{_new_bot}] / {canvas_h} "
                                f"(−{_new_top}top, −{canvas_h - _new_bot}bot)"
                            )
                else:
                    # Horizontal scroll: trim pure-bg columns at left/right
                    _col_has_fg = _union_fg.any(axis=0)  # (canvas_w,)
                    _fg_cols = np.where(_col_has_fg)[0]
                    if len(_fg_cols) > 0:
                        _cap_px = int(canvas_w * _trim_cap_frac)
                        _new_lft = max(0, min(int(_fg_cols[0]), _cap_px))
                        _new_rgt = min(
                            canvas_w, max(int(_fg_cols[-1]) + 1, canvas_w - _cap_px)
                        )
                        if _new_lft > 0 or _new_rgt < canvas_w:
                            canvas = canvas[:, _new_lft:_new_rgt]
                            valid_mask = valid_mask[:, _new_lft:_new_rgt]
                            logger.info(
                                f"[Stitch] Stage 12.5: horizontal scroll content trim "
                                f"cols [{_new_lft}:{_new_rgt}] / {canvas_w} "
                                f"(−{_new_lft}left, −{canvas_w - _new_rgt}right)"
                            )
        except Exception as _trim_e:
            logger.debug(f"[Stitch] Stage 12.5 content trim skipped ({_trim_e}).")

        # ── Stage 13: Morphological boundary crop ───────────────────────────
        canvas = _crop_to_valid(canvas, valid_mask)
        if getattr(self, "edge_crop", 0) > 0:
            ec = self.edge_crop
            if ec * 2 < canvas.shape[0] and ec * 2 < canvas.shape[1]:
                canvas = canvas[ec:-ec, ec:-ec]
        logger.info("[Stitch] Stage 13 complete: boundary crop done.")

        # P1.8 — Auto-trigger diffusion inpainting for coverage gaps (W4 fix).
        # test7 (diagonal motion) leaves black corners at 81.5% coverage.
        # After the crop, recalculate the valid-pixel ratio and call the existing
        # inpaint_gaps module when coverage drops below 95%.
        _gap_mask = (canvas.max(axis=2) == 0).astype(np.uint8) * 255
        _coverage = 1.0 - float(_gap_mask.mean()) / 255.0
        if _coverage < 0.95 and _gap_mask.any():
            logger.debug(
                f"[Stitch]   Coverage {_coverage * 100:.1f}% < 95%; "
                f"auto-activating border fill for black corners."
            )
            try:
                canvas = _telea_fill_gaps(canvas, _gap_mask)
                logger.info("[Stitch]   TELEA border fill complete.")
            except Exception as _telea_e:
                logger.info(
                    f"[Stitch]   TELEA border fill failed ({_telea_e}); keeping canvas as-is."
                )

        # ── Save ─────────────────────────────────────────────────────────────
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out = Image.fromarray(rgb)
        out.save(output_path)
        gc.collect()
        logger.info(f"[Stitch] Done. Saved to '{output_path}'.")

        return out

    # ------------------------------------------------------------- thin wrappers
    # The original class exposed several stage methods (as bound or static).
    # We keep them as thin wrappers so external callers (tests, helpers) still
    # work.

    def _load_frames(self, paths: List[str]) -> List[np.ndarray]:
        return _load_frames(paths)

    @staticmethod
    def _normalise_widths(frames: List[np.ndarray]) -> List[np.ndarray]:
        return _normalise_widths(frames)

    def _apply_basic(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        if self._basic is None:
            self._basic = BaSiCWrapper()
        corrected, baselines = _apply_basic(frames, self._basic)
        self._baselines = baselines
        return corrected

    def _correct_vignetting(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        return _correct_vignetting(frames)

    def _compute_fg_masks(self, frames: List[np.ndarray]) -> List[Optional[np.ndarray]]:
        if self.use_birefnet and self._birefnet is None:
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )  # §3.14 lazy

            self._birefnet = BiRefNetWrapper()
        if _USE_SAM2:
            masks, pred, state, tmp, fh, fw = _compute_fg_masks_sam2_stateful(
                frames, self._birefnet, use_birefnet=self.use_birefnet
            )
            self._sam2_predictor = pred
            self._sam2_inference_state = state
            self._sam2_tmp_dir = tmp
            self._sam2_frame_h = fh
            self._sam2_frame_w = fw
            return masks
        return _compute_fg_masks(frames, self._birefnet, use_birefnet=self.use_birefnet)

    def _cleanup_sam2_state(self) -> None:
        """Free the live SAM-2 predictor state stored by _compute_fg_masks."""
        _cleanup_sam2_state(
            self._sam2_predictor, self._sam2_inference_state, self._sam2_tmp_dir
        )
        self._sam2_predictor = None
        self._sam2_inference_state = None
        self._sam2_tmp_dir = None
        self._sam2_frame_h = 0
        self._sam2_frame_w = 0

    def _pairwise_match(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[Dict]:
        if self.use_loftr and self._loftr is None:
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper  # §3.14 lazy

            self._loftr = LoFTRWrapper()
        return _pairwise_match(
            frames,
            bg_masks,
            loftr_wrapper=self._loftr,
            use_loftr=self.use_loftr,
            motion_model=self.motion_model,
            aliked_wrapper=self._aliked if self.use_aliked else None,
        )

    def _match_pair(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        i: int,
        j: int,
        H: int,
        W: int,
    ) -> Optional[Dict]:
        return _match_pair(
            frames,
            bg_masks,
            i,
            j,
            H,
            W,
            loftr_wrapper=self._loftr,
            use_loftr=self.use_loftr,
            motion_model=self.motion_model,
            aliked_wrapper=self._aliked if self.use_aliked else None,
        )

    @staticmethod
    def _template_match(
        img_i: np.ndarray,
        img_j: np.ndarray,
        m_i: Optional[np.ndarray],
        m_j: Optional[np.ndarray],
        H: int,
        slice_h: int = 256,
        max_search_frac: float = 0.8,
        direction_sign: int = 0,
        max_dy_frac: float = 0.70,
    ) -> Tuple[Optional[np.ndarray], float]:
        return _template_match(
            img_i,
            img_j,
            m_i,
            m_j,
            H,
            slice_h=slice_h,
            max_search_frac=max_search_frac,
            direction_sign=direction_sign,
            max_dy_frac=max_dy_frac,
        )

    @staticmethod
    def _phase_correlate(
        img_i: np.ndarray,
        img_j: np.ndarray,
        m_i: Optional[np.ndarray],
        m_j: Optional[np.ndarray],
        use_mask: bool = True,
    ) -> Tuple[Optional[np.ndarray], float]:
        return _phase_correlate(img_i, img_j, m_i, m_j, use_mask=use_mask)

    @staticmethod
    def _sample_bg_points(
        mask: Optional[np.ndarray], H: int, W: int, n: int = 200
    ) -> np.ndarray:
        return _sample_bg_points(mask, H, W, n=n)

    def _ecc_refine(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[np.ndarray]:
        return _ecc_refine(frames, affines, bg_masks)

    @staticmethod
    def _compute_canvas(
        frames: List[np.ndarray],
        affines: List[np.ndarray],
    ) -> Tuple[int, int, np.ndarray]:
        return _compute_canvas(frames, affines)

    def _render(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        canvas_h: int,
        canvas_w: int,
    ) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
        return _render(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            renderer=self.renderer,
            baselines=self._baselines,
        )

    def _render_median(self, *args, **kwargs):
        return _render_median(*args, **kwargs)

    def _render_first(self, frames, affines, H, W):
        return _render_first(frames, affines, H, W)

    def _render_laplacian(self, *args, **kwargs):
        return _render_laplacian(*args, **kwargs)

    @staticmethod
    def _cluster_animation_phases(
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        H: int,
        W: int,
        target_w: int = 320,
        ac_threshold: float = 0.25,
        min_anim_pixels: int = 500,
    ):
        return _cluster_animation_phases(
            frames,
            affines,
            H,
            W,
            target_w=target_w,
            ac_threshold=ac_threshold,
            min_anim_pixels=min_anim_pixels,
        )

    def _composite_foreground(
        self,
        warped_corr: List[np.ndarray],
        warped_fgs: List[np.ndarray],
        canvas: np.ndarray,
        H: int,
        W: int,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        frame_keys: Optional[Tuple[str, ...]] = None,
        seam_path_cache: Optional[Dict] = None,
        exclusion_masks: Optional[List[np.ndarray]] = None,
        preset_boundaries: Optional[np.ndarray] = None,
        paint_mask: Optional[np.ndarray] = None,
        seam_meta_out: Optional[dict] = None,
        seam_overrides: Optional[dict] = None,
    ) -> np.ndarray:
        return _composite_foreground(
            warped_corr,
            warped_fgs,
            canvas,
            H,
            W,
            frames,
            affines,
            bg_masks,
            frame_keys=frame_keys,
            seam_path_cache=seam_path_cache,
            exclusion_masks=exclusion_masks,
            preset_boundaries=preset_boundaries,
            paint_mask=paint_mask,
            seam_meta_out=seam_meta_out,
            seam_overrides=seam_overrides,
        )

    def _crop_to_valid(self, canvas: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        return _crop_to_valid(canvas, valid_mask)

    @staticmethod
    def _scan_stitch_fallback(
        frames: List[np.ndarray],
        output_path: str,
    ) -> Image.Image:
        return _scan_stitch_fallback(frames, output_path)

    @staticmethod
    def find_optimal_sequence(
        ref_path: str,
        candidates: List[str],
        min_inliers: int = 30,
        max_overlap: float = 0.85,
    ) -> List[str]:
        return find_optimal_sequence(
            ref_path,
            candidates,
            min_inliers=min_inliers,
            max_overlap=max_overlap,
        )


def _build_manual_edge(
    i: int,
    j: int,
    dx: float,
    dy: float,
    weight: float = 0.9,
) -> Dict:
    """§S89: Construct a pipeline-compatible edge dict from a user-supplied displacement.

    The affine M is a pure translation: [[1, 0, dx], [0, 1, dy]].
    pts_i / pts_j are set to a single centroid-estimate point so Bundle Adjust
    can process the edge without matched feature points.

    Args:
        i: Source frame index.
        j: Target frame index.
        dx: Horizontal pixel displacement (j relative to i).
        dy: Vertical pixel displacement (j relative to i).
        weight: Edge confidence weight in [0, 1]; default 0.9 (high confidence
                for manual edges since the user deliberately chose the value).

    Returns:
        Edge dict compatible with ``_bundle_adjust_affine`` and the HITL edge
        override path in ``StitchWorker``.
    """
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float64)
    pts_i = np.array([[0.0, 0.0]], dtype=np.float32)
    pts_j = np.array([[dx, dy]], dtype=np.float32)
    return {
        "i": i,
        "j": j,
        "M": M,
        "pts_i": pts_i,
        "pts_j": pts_j,
        "weight": float(np.clip(weight, 0.0, 1.0)),
        "method": "manual",
    }


def _build_landmark_affine(
    i: int,
    j: int,
    landmark_pairs: "List[Tuple[Tuple[float, float], Tuple[float, float]]]",
    weight: float = 0.95,
) -> Dict:
    """§2.9A: Build a pipeline edge dict from user-placed landmark point pairs.

    Constructs a least-squares affine (or partial-affine / translation) from
    the N landmark correspondences provided by the BigWarp landmark editor
    dialog and returns an edge dict compatible with ``_bundle_adjust_affine``.

    ``landmark_pairs`` is a list of ``((xi, yi), (xj, yj))`` tuples where
    ``(xi, yi)`` is the point in frame i and ``(xj, yj)`` is the corresponding
    point in frame j, both in pixel coordinates.

    Estimation strategy (by point count):
    - 1 pair  → pure translation (centroid-to-centroid displacement)
    - 2 pairs → ``cv2.estimateAffinePartial2D`` (4-DOF: tx, ty, rotation, scale)
    - 3+ pairs → ``cv2.estimateAffine2D`` (6-DOF general affine, LMEDS robust)

    Falls back to centroid translation if cv2 estimation returns None/fails.

    Args:
        i: Source frame index.
        j: Target frame index.
        landmark_pairs: At least 1 ``((xi, yi), (xj, yj))`` correspondence.
        weight: Edge confidence weight in [0, 1]; default 0.95.

    Returns:
        Edge dict compatible with ``_bundle_adjust_affine`` and the HITL edge
        override path in ``StitchWorker``.
    """
    if not landmark_pairs:
        raise ValueError("landmark_pairs must contain at least 1 point pair")

    pts_i = np.array([[p[0][0], p[0][1]] for p in landmark_pairs], dtype=np.float32)
    pts_j = np.array([[p[1][0], p[1][1]] for p in landmark_pairs], dtype=np.float32)

    M: Optional[np.ndarray] = None
    n = len(landmark_pairs)
    if n >= 3:
        M_est, inliers = cv2.estimateAffine2D(pts_i, pts_j, method=cv2.LMEDS)
        if M_est is not None:
            M = M_est.astype(np.float64)
    elif n == 2:
        M_est, inliers = cv2.estimateAffinePartial2D(pts_i, pts_j, method=cv2.LMEDS)
        if M_est is not None:
            M = M_est.astype(np.float64)

    if M is None:
        # Centroid translation fallback
        centroid_i = pts_i.mean(axis=0)
        centroid_j = pts_j.mean(axis=0)
        dx = float(centroid_j[0] - centroid_i[0])
        dy = float(centroid_j[1] - centroid_i[1])
        M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float64)

    return {
        "i": i,
        "j": j,
        "M": M,
        "pts_i": pts_i,
        "pts_j": pts_j,
        "weight": float(np.clip(weight, 0.0, 1.0)),
        "method": "landmark",
    }


__all__ = [
    "AnimeStitchPipeline",
    "_ALIKED_OK",
    "_BIREFNET_OK",
    "_DY_CV_MAX",
    "_ELOFTR_OK",
    "_LOFTR_OK",
    "_USE_SAM2",
    "_apply_hires_keyframes",
    "_build_landmark_affine",
    "_build_manual_edge",
    "_check_edge_graph_connectivity",
    "_compute_adaptive_dy_cv_max",
    "_compute_adaptive_min_disp",
    "_compute_dy_cv",
    "_compute_row_coverage",
    "_filter_high_conf_edges",
    "_reject_static_edges",
    "_reload_scans_frames",
    "_sort_frames_by_index",
    "_spatial_dedup_frames",
    "logger",
]
