"""
AnimeStitchPipeline — top-level orchestrator.

Delegates each pipeline stage to its sibling module (matching, photometric,
masking, ECC, rendering, compositing, canvas, bundle adjustment).  Optionally
runs the MFSR super-resolution pass after stage 10 when ``mfsr_mode=True``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import os

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import gc
import re
import warnings
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image

from .bundle_adjust import _bundle_adjust_affine
from .validation import _validate_affines
from .canvas import (
    _compute_canvas,
    _crop_to_valid,
    _load_frames,
    _normalise_widths,
    _scan_stitch_fallback,
    find_optimal_sequence,
)
from .compositing import _composite_foreground
from backend.src.constants import (
    LAPLACIAN_BANDS,
    MATCH_EDGE_CROP,
    MIN_EXPECTED_STEP,
)
from .ecc import _ecc_refine
from .masking import _compute_fg_masks
from .matching import (
    _match_pair,
    _pairwise_match,
    _phase_correlate,
    _sample_bg_points,
    _sample_bg_points_grid,
    _template_match,
)
from .photometric import _apply_basic, _correct_vignetting
from .rendering import (
    _cluster_animation_phases,
    _render,
    _render_first,
    _render_laplacian,
    _render_median,
)

# Optional heavy dependencies — guarded imports
try:
    from backend.src.models.basic_wrapper import BaSiCWrapper

    _BASIC_OK = True
except ImportError:
    _BASIC_OK = False

try:
    from backend.src.models.birefnet_wrapper import BiRefNetWrapper

    _BIREFNET_OK = True
except ImportError:
    _BIREFNET_OK = False

try:
    from backend.src.models.loftr_wrapper import LoFTRWrapper

    _LOFTR_OK = True
except ImportError:
    _LOFTR_OK = False

try:
    from backend.src.models.efficient_loftr_wrapper import EfficientLoFTRWrapper

    _ELOFTR_OK = True
except ImportError:
    _ELOFTR_OK = False

try:
    from backend.src.models.stitch_net import AnimeStitchNet

    _STITCH_NET_OK = True
except ImportError:
    _STITCH_NET_OK = False

try:
    from backend.src.models.aliked_lg_wrapper import ALIKEDLightGlueWrapper

    _ALIKED_OK = True
except ImportError:
    _ALIKED_OK = False

try:
    from backend.src.models.roma_wrapper import RoMaWrapper

    _ROMA_OK = True
except ImportError:
    _ROMA_OK = False

try:
    from .flow_refine import _flow_refine, _load_sea_raft

    _SEA_RAFT_OK = True
except ImportError:
    _SEA_RAFT_OK = False

try:
    from .super_res import upscale_anime, _UPSCALE_OK as _SR_OK
except ImportError:
    _SR_OK = False

try:
    from .anim_fill import tooncrafter_ghost_fill

    _TOONCRAFTER_OK = True
except ImportError:
    _TOONCRAFTER_OK = False

try:
    from .sr_stitcher import (
        seam_diffusion_fusion,
        border_diffusion_fill,
        _DIFFUSERS_OK as _SRSTITCHER_OK,
    )
except ImportError:
    _SRSTITCHER_OK = False


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
    mfsr_mode    : when True, runs the MFSR super-resolution pipeline after the
                   temporal render (stage 10) to sharpen edges and reverse
                   compression artifacts.
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
        sr_mode: bool = False,
        sr_scale: int = 2,
        use_ecc: bool = True,
        renderer: str = "median",  # 'median' | 'first' | 'blend'
        composite_fg: bool = True,
        laplacian_bands: int = LAPLACIAN_BANDS,
        stitch_net_ckpt: str = "",  # path to AnimeStitchNet checkpoint
        edge_crop: int = 30,
        motion_model: str = "translation",  # 'translation' or 'affine' (4-DOF)
        mfsr_mode: bool = False,
        mfsr_n_dct_iter: int = 20,
        mfsr_use_prior: bool = True,
        mfsr_use_diffusion: bool = False,
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
        self.sr_mode = sr_mode and _SR_OK
        self.sr_scale = sr_scale
        self.use_tooncrafter = kwargs.get("use_tooncrafter", False) and _TOONCRAFTER_OK
        self.use_srstitcher = kwargs.get("use_srstitcher", False) and _SRSTITCHER_OK
        self.use_jamma = kwargs.get("use_jamma", False)
        self.use_ecc = use_ecc
        self.renderer = renderer
        self.composite_fg = composite_fg
        self.bands = laplacian_bands
        self.stitch_net_ckpt = stitch_net_ckpt
        self.edge_crop = edge_crop
        self.motion_model = motion_model
        self.mfsr_mode = mfsr_mode
        self.mfsr_n_dct_iter = mfsr_n_dct_iter
        self.mfsr_use_prior = mfsr_use_prior
        self.mfsr_use_diffusion = mfsr_use_diffusion

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

    def _filter_edges(
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
        # ── Geometric Consistency Filter ─────────────────────────────────────
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

        # ── Min-step guard ─────────────────────────────────────────────────────
        # Reject adjacent edges with near-zero displacement BEFORE the direction consensus
        # filter.  When the majority of edges are near-zero (test8/test9/test16),
        # the consensus median is also near-zero and the filter cannot distinguish
        # good from bad.  This guard prevents the inverted-consensus pattern.
        
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

    def run(
        self,
        image_paths: List[str],
        output_path: str,
    ) -> Image.Image:
        """
        Execute the full stitching pipeline.

        Parameters
        ----------
        image_paths : ordered list of source frame paths (first = leftmost/topmost).
        output_path : destination PNG/WEBP path.

        Returns
        -------
        PIL.Image of the final stitched panorama.
        """
        # Exclude the output file if it was accidentally included in the input list.
        out_abs = os.path.abspath(output_path)
        image_paths = [p for p in image_paths if os.path.abspath(p) != out_abs]

        logger.info(f"[Stitch] Starting AnimeStitchPipeline on {len(image_paths)} frames.")
        self._baselines = None

        # ── Stage 1: Load & trim ─────────────────────────────────────────────
        frames = _load_frames(image_paths)
        N = len(frames)
        if N < 2:
            raise ValueError("Need at least 2 valid frames to stitch.")
        logger.info(f"[Stitch] Stage 1 complete: {N} frames loaded.")

        # ── Stage 2: Width normalisation ─────────────────────────────────────
        frames = _normalise_widths(frames)
        H, W = frames[0].shape[:2]
        scans_frames = list(
            frames
        )  # snapshot before ML corrections — used for SCANS fallback
        logger.info(f"[Stitch] Stage 2 complete: all frames at {W}×{H}.")

        # ── Stage 3: BaSiC photometric correction ────────────────────────────
        if self.use_basic:
            if self._basic is None:
                self._basic = BaSiCWrapper()
            frames, baselines = _apply_basic(frames, self._basic)
            self._baselines = baselines
            frames = _correct_vignetting(frames)
            logger.info("[Stitch] Stage 3 complete: BaSiC + Vignette correction applied.")
        else:
            logger.info("[Stitch] Stage 3 skipped (use_basic=False).")

        # ── Stage 4: Foreground masking ──────────────────────────────────────
        if self.use_birefnet and self._birefnet is None:
            self._birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(
            frames,
            self._birefnet,
            use_birefnet=self.use_birefnet,
        )
        if self._birefnet is not None:
            try:
                self._birefnet.unload()
            except Exception:
                pass
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
        for _i, (_frame, _mask) in enumerate(zip(frames, bg_masks)):
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
                if diff < 3.0:
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
                scans_frames = [scans_frames[i] for i in keep_idx]
                bg_masks = [bg_masks[i] for i in keep_idx]
                image_paths = [image_paths[i] for i in keep_idx]
                N = len(frames)
                logger.debug(
                    f"[Stitch]   Dedup complete: {sum(not k for k in keep)} "
                    f"removed, {N} remain."
                )
                if N < 2:
                    return _scan_stitch_fallback(scans_frames, output_path)

        # ── Stage 5-6: Pairwise matching (+ skip-pair edges) ────────────────
        # ── Matcher selection (P1.4 EfficientLoFTR / P3.2 JamMa) ───────────────
        # Priority: JamMa (4K only) → EfficientLoFTR → kornia LoFTR → None.
        _is_4k = H * W > 3000 * 2000
        _active_loftr = None

        if self.use_jamma and _is_4k:
            try:
                from backend.src.models.jamma_wrapper import JamMaWrapper

                _jamma_inst = JamMaWrapper()
                _jamma_inst.load_model()
                _active_loftr = _jamma_inst
                logger.info(f"[Stitch]   4K frame ({W}×{H}): using JamMa (O(N) Mamba).")
            except Exception as _jm_e:
                logger.info(f"[Stitch]   JamMa unavailable ({_jm_e}); using EfficientLoFTR.")

        # P1.4 — Use EfficientLoFTR (2.5× faster) when available; fall back to
        # kornia LoFTR.  Both expose the same .match() interface.
        if _active_loftr is None and self.use_efficient_loftr:
            if self._eloftr is None:
                try:
                    self._eloftr = EfficientLoFTRWrapper()
                    self._eloftr.load_model()
                    _active_loftr = self._eloftr
                    logger.info("[Stitch]   Using EfficientLoFTR (2.5× faster than LoFTR).")
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
                self._loftr = LoFTRWrapper()
            _active_loftr = self._loftr

        if self.use_aliked and self._aliked is None:
            try:
                self._aliked = ALIKEDLightGlueWrapper()
            except Exception as _e:
                logger.info(f"[Stitch]   ALIKED+LightGlue init failed ({_e}); disabling.")
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
        
        _spa_changed = True
        _total_spa_dropped = 0
        while _spa_changed:
            _spa_changed = False
            _adj_m = {e["j"]: e for e in edges if e["j"] == e["i"] + 1}
            if not _adj_m:
                break
            _adx = [abs(float(e["M"][0, 2])) for e in _adj_m.values()]
            _ady = [abs(float(e["M"][1, 2])) for e in _adj_m.values()]
            _spa_axis = 0 if float(np.median(_adx)) > float(np.median(_ady)) else 1
            _drop: set = set()
            for _jj in sorted(_adj_m):
                _ee = _adj_m[_jj]
                if _ee["i"] in _drop:
                    continue
                if abs(float(_ee["M"][_spa_axis, 2])) < SPATIAL_DEDUP_PX:
                    _drop.add(_jj)
                    _spa_changed = True
                    logger.debug(
                        f"[Stitch]   Spatial dedup: frame {_jj} ≈ frame {_ee['i']} "
                        f"(d{'x' if _spa_axis == 0 else 'y'}="
                        f"{float(_ee['M'][_spa_axis, 2]):.1f}px) — dropped."
                    )
            if _drop:
                _total_spa_dropped += len(_drop)
                _keep_idx = [i for i in range(N) if i not in _drop]
                frames = [frames[i] for i in _keep_idx]
                bg_masks = [bg_masks[i] for i in _keep_idx]
                image_paths = [image_paths[i] for i in _keep_idx]
                _o2n = {old: new for new, old in enumerate(_keep_idx)}
                edges = [
                    {**e, "i": _o2n[e["i"]], "j": _o2n[e["j"]]}
                    for e in edges
                    if e["i"] not in _drop and e["j"] not in _drop
                ]
                N = len(frames)
                if N < 2:
                    return _scan_stitch_fallback(scans_frames, output_path)
        if _total_spa_dropped:
            logger.debug(
                f"[Stitch]   Spatial dedup complete: {_total_spa_dropped} frames "
                f"removed, {N} remain."
            )

        edges = self._filter_edges(edges, image_paths, H, W, frames, bg_masks)

        for _mdl in [self._loftr, self._eloftr, self._aliked, self._roma]:
            if _mdl is not None:
                try:
                    _mdl.unload()
                except Exception:
                    try:
                        _mdl.offload()
                    except Exception:
                        pass
        self._loftr = None
        self._eloftr = None
        self._aliked = None
        self._roma = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        logger.info(f"[Stitch] Stages 5-6 complete: {len(edges)} valid edges found.")
        if not edges:
            warnings.warn("[Stitch] No valid edges — falling back to scan stitch.")
            return _scan_stitch_fallback(scans_frames, output_path)

        # ── Stage 7: Global bundle adjustment ────────────────────────────────
        use_affine_ba = getattr(self, "motion_model", "affine") == "affine"
        affines = _bundle_adjust_affine(edges, N, use_affine=use_affine_ba)
        logger.debug(
            f"[Stitch] Stage 7 complete: bundle adjustment done "
            f"(mode={'affine' if use_affine_ba else 'translation'})."
        )

        # ── Stage 7b: Affine validation gate ─────────────────────────────────
        health = _validate_affines(affines)
        logger.debug(
            f"[Stitch]   Affine health: valid={health.valid}, "
            f"ratio={health.ratio:.1f}×, min_gap={health.min_gap:.0f}px, "
            f"max_rot={health.max_rotation:.4f}, scale_dev={health.max_scale_dev:.4f}"
        )
        if not health.valid:
            logger.debug(
                f"[Stitch]   Affine health FAILED ({health.reason}); attempting recovery..."
            )
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
                        if _e["j"] == _f and _e["i"] in _anchored:
                            if _f - _e["i"] < _best_span:
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
                            if _e["j"] == _f and _e["i"] in _anchored:
                                if _f - _e["i"] < _best_span:
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
                warnings.warn(
                    f"[Stitch] Affine validation FAILED ({health.reason}) after retries. "
                    f"Falling back to SCANS stitch."
                )
                return _scan_stitch_fallback(scans_frames, output_path)

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
                    try:
                        self._sea_raft.cpu()
                    except Exception:
                        pass
                    torch.cuda.empty_cache()
                    self._sea_raft = None
            except Exception as _ecc_e:
                logger.info(f"[Stitch]   SEA-RAFT failed ({_ecc_e}); falling back to ECC.")
                if self.use_ecc:
                    affines = _ecc_refine(frames, affines, bg_masks)
                    logger.info("[Stitch] Stage 8 complete: ECC refinement done (fallback).")
        elif self.use_ecc:
            affines = _ecc_refine(frames, affines, bg_masks)
            logger.info("[Stitch] Stage 8 complete: ECC refinement done.")
        else:
            logger.info("[Stitch] Stage 8 skipped (use_ecc=False, use_sea_raft=False).")

        # ── Stage 9: Canvas construction ────────────────────────────────────
        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        logger.info(f"[Stitch] Stage 9: canvas size {canvas_w}×{canvas_h}.")
        if canvas_h <= 0 or canvas_w <= 0:
            raise RuntimeError("Computed canvas has zero size.")

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

        # ── Optional: MFSR super-resolution pass ─────────────────────────────
        # P1.7 — Auto-activate MFSR for low-sharpness canvas (W1 fix).
        # Tests 2, 3, 19, 20 produce Laplacian variance 12–16 from inherently
        # blurry/dark sources.  If the canvas is below threshold and MFSR is
        # not already requested, trigger it automatically.
        _lap_var: float = float(
            cv2.Laplacian(cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        )
        _mfsr_active = self.mfsr_mode
        if not _mfsr_active and _lap_var < 20.0:
            logger.debug(
                f"[Stitch]   Low sharpness detected (Laplacian var={_lap_var:.1f} < 20); "
                f"auto-activating MFSR."
            )
            _mfsr_active = True

        if _mfsr_active:
            try:
                from .mfsr import run_mfsr

                canvas = run_mfsr(
                    frames,
                    affines,
                    canvas_h,
                    canvas_w,
                    quality=75,
                    use_prior=self.mfsr_use_prior,
                    use_diffusion_inpaint=self.mfsr_use_diffusion,
                    n_dct_iter=self.mfsr_n_dct_iter,
                )
                # Refresh the valid mask to the new canvas's non-zero pixels.
                valid_mask = (canvas.max(axis=2) > 0).astype(np.uint8) * 255
                logger.info("[Stitch]   MFSR refinement complete.")
            except Exception as e:
                logger.debug(
                    f"[Stitch]   MFSR refinement failed ({e}); keeping median canvas."
                )

        # P3.3 — ToonCrafter ghost fill (after temporal render, before fg composite).
        # Uses _cluster_animation_phases output (already computed inside _render_median)
        # to replace ghosted animation pixels with a ToonCrafter canonical cel.
        if self.use_tooncrafter and N >= 4:
            try:
                from .rendering import _cluster_animation_phases

                _dev_tc = "cuda" if torch.cuda.is_available() else "cpu"
                _tc_anim_mask, _tc_phase_groups = _cluster_animation_phases(
                    frames, affines, canvas_h, canvas_w
                )
                if _tc_anim_mask is not None and _tc_phase_groups is not None:
                    canvas = tooncrafter_ghost_fill(
                        canvas,
                        _tc_anim_mask,
                        _tc_phase_groups,
                        frames,
                        affines,
                        device=_dev_tc,
                    )
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
            except Exception as _tc_e:
                logger.info(f"[Stitch]   ToonCrafter ghost fill failed ({_tc_e}); skipping.")

        # ── Stage 11: Foreground composite ──────────────────────────────────
        if self.composite_fg and self.use_birefnet:
            canvas = _composite_foreground(
                [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks
            )
            logger.info("[Stitch] Stage 11 complete: foreground composited.")

        # P3.4 — SRStitcher seam diffusion fusion (Stage 11.5).
        # Inpaints the seam bands using a diffusion model so hard Laplacian
        # transitions are replaced by style-consistent anime content.
        if self.use_srstitcher:
            try:
                _dev_sr2 = "cuda" if torch.cuda.is_available() else "cpu"
                # Compute seam y-positions from affine boundaries
                _tys = [float(affines[k][1, 2]) for k in range(N)]
                _ctrs = [_tys[k] + frames[k].shape[0] / 2.0 for k in range(N)]
                _order = np.argsort(_ctrs)
                _sorted_ctrs = [_ctrs[_order[k]] for k in range(N)]
                _seam_ys = [
                    int((_sorted_ctrs[k] + _sorted_ctrs[k + 1]) / 2.0)
                    for k in range(N - 1)
                ]
                canvas = seam_diffusion_fusion(
                    canvas, _seam_ys, device=_dev_sr2, num_steps=20
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info("[Stitch] Stage 11.5 complete: SRStitcher seam diffusion done.")
            except Exception as _srs_e:
                logger.info(f"[Stitch]   SRStitcher seam fusion failed ({_srs_e}); skipping.")

        # ── Stage 12: Remaining seam blend (handled inside _render). ────────

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
                f"auto-activating diffusion inpainting for black corners."
            )
            try:
                from .mfsr import inpaint_gaps

                canvas = inpaint_gaps(canvas, gap_mask=_gap_mask)
                logger.info("[Stitch]   Inpainting complete.")
            except Exception as _e:
                logger.info(f"[Stitch]   Inpainting failed ({_e}); keeping canvas as-is.")

        # ── Optional: Real-ESRGAN anime_6B super-resolution (P2.2) ──────────
        if self.sr_mode and _SR_OK:
            try:
                _dev_sr = "cuda" if torch.cuda.is_available() else "cpu"
                logger.debug(
                    f"[Stitch]   Running Real-ESRGAN anime_6B {self.sr_scale}× SR "
                    f"on {canvas.shape[1]}×{canvas.shape[0]} canvas…"
                )
                canvas = upscale_anime(canvas, scale=self.sr_scale, device=_dev_sr)
                logger.debug(
                    f"[Stitch]   SR complete: output {canvas.shape[1]}×{canvas.shape[0]}."
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as _sr_e:
                logger.debug(
                    f"[Stitch]   Real-ESRGAN failed ({_sr_e}); keeping original resolution."
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
            self._birefnet = BiRefNetWrapper()
        return _compute_fg_masks(frames, self._birefnet, use_birefnet=self.use_birefnet)

    def _pairwise_match(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[Dict]:
        if self.use_loftr and self._loftr is None:
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
    ) -> np.ndarray:
        return _composite_foreground(
            warped_corr, warped_fgs, canvas, H, W, frames, affines, bg_masks
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


__all__ = ["AnimeStitchPipeline"]