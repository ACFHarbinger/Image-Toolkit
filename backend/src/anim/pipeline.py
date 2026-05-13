"""
AnimeStitchPipeline — top-level orchestrator.

Delegates each pipeline stage to its sibling module (matching, photometric,
masking, ECC, rendering, compositing, canvas, bundle adjustment).  Optionally
runs the MFSR super-resolution pass after stage 10 when ``mfsr_mode=True``.
"""

from __future__ import annotations

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
from .canvas import (
    _compute_canvas,
    _crop_to_valid,
    _load_frames,
    _normalise_widths,
    _scan_stitch_fallback,
    find_optimal_sequence,
)
from .compositing import _composite_foreground
from .constants import (
    _LAPLACIAN_BANDS,
    _MATCH_EDGE_CROP,
)
from .ecc import _ecc_refine
from .masking import _compute_fg_masks
from .matching import (
    _match_pair,
    _pairwise_match,
    _phase_correlate,
    _sample_bg_points,
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
    from backend.src.models.stitch_net import AnimeStitchNet

    _STITCH_NET_OK = True
except ImportError:
    _STITCH_NET_OK = False


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
        use_ecc: bool = True,
        renderer: str = "median",  # 'median' | 'first' | 'blend'
        composite_fg: bool = True,
        laplacian_bands: int = _LAPLACIAN_BANDS,
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
                        print(
                            f"[Stitch]   Edge {i}→{j} rejected: inconsistency "
                            f"(dx={diff_x:.1f}, dy={diff_y:.1f})"
                        )
                else:
                    filtered.append(e)
            edges = filtered

        # ── Direction Consensus Filter ────────────────────────────────────────
        if len(edges) >= 3:
            adj_dys = [e["M"][1, 2] for e in edges if e["j"] == e["i"] + 1]
            if len(adj_dys) >= 3:
                median_dy = float(np.median(adj_dys))
                consensus_sign = int(np.sign(median_dy))

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

                def _wrong_sign(dy_val: float) -> bool:
                    return (
                        consensus_sign != 0
                        and np.sign(dy_val) != 0
                        and int(np.sign(dy_val)) != consensus_sign
                    )

                def _gross_outlier(dy_val: float) -> bool:
                    return (
                        abs(dy_val) > 2.0 * abs(median_dy)
                        and abs(dy_val - median_dy) > 200.0
                    )

                vel_samples = []
                for e in edges:
                    if e["j"] != e["i"] + 1:
                        continue
                    dy_e = float(e["M"][1, 2])
                    if _wrong_sign(dy_e) or _gross_outlier(dy_e):
                        continue
                    iv = _interval_ms(e["i"], e["j"])
                    if iv is not None:
                        vel_samples.append(dy_e / iv)
                vel_px_per_ms: Optional[float] = (
                    float(np.median(vel_samples)) if vel_samples else None
                )
                if vel_px_per_ms is not None:
                    print(
                        f"[Stitch]   Scroll velocity: {vel_px_per_ms:.4f} px/ms "
                        f"(from {len(vel_samples)} reliable edges)"
                    )

                def _is_outlier(dy_val: float, fi: int, fj: int) -> Tuple[bool, str]:
                    if _wrong_sign(dy_val):
                        return True, "wrong sign"
                    if _gross_outlier(dy_val):
                        return True, "gross outlier"
                    if vel_px_per_ms is not None:
                        iv = _interval_ms(fi, fj)
                        if iv is not None:
                            expected = abs(vel_px_per_ms) * iv
                            if abs(dy_val - expected * consensus_sign) > max(
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

                ec_h = int(H * _MATCH_EDGE_CROP)
                ec_w = int(W * _MATCH_EDGE_CROP)
                corrected: List[Dict] = []
                for e in edges:
                    if e["j"] == e["i"] + 1:
                        fi, fj = e["i"], e["j"]
                        dy = float(e["M"][1, 2])
                        outlier, reason = _is_outlier(dy, fi, fj)
                        if outlier:
                            iv = _interval_ms(fi, fj)
                            replaced = False
                            if vel_px_per_ms is not None and iv is not None:
                                est_dy = vel_px_per_ms * iv
                                print(
                                    f"[Stitch]   Edge {fi}→{fj}: dy={dy:.1f} ({reason}); "
                                    f"velocity → dy={est_dy:.1f}"
                                )
                                M_fix = np.eye(2, 3, dtype=np.float32)
                                M_fix[0, 2] = e["M"][0, 2]
                                M_fix[1, 2] = est_dy
                                e = _apply_corrected_M(e, M_fix, 0.55)
                                replaced = True
                            if not replaced:
                                img_i_c = frames[fi][ec_h:-ec_h, ec_w:-ec_w]
                                img_j_c = frames[fj][ec_h:-ec_h, ec_w:-ec_w]
                                m_i_c = (
                                    bg_masks[fi][ec_h:-ec_h, ec_w:-ec_w]
                                    if bg_masks[fi] is not None
                                    else None
                                )
                                M_dir, c_dir = _template_match(
                                    img_i_c, img_j_c, m_i_c, None,
                                    img_i_c.shape[0], direction_sign=consensus_sign,
                                )
                                if (
                                    M_dir is not None
                                    and int(np.sign(M_dir[1, 2])) == consensus_sign
                                ):
                                    new_dy = float(M_dir[1, 2])
                                    print(
                                        f"[Stitch]   Edge {fi}→{fj}: directed TM → "
                                        f"dy={new_dy:.1f} conf={c_dir:.3f}"
                                    )
                                    M_new = np.array(
                                        [[1, 0, e["M"][0, 2]], [0, 1, new_dy]],
                                        dtype=np.float32,
                                    )
                                    e = _apply_corrected_M(e, M_new, c_dir * 0.7)
                                    replaced = True
                            if not replaced:
                                print(
                                    f"[Stitch]   Edge {fi}→{fj}: dy={dy:.1f} ({reason}); "
                                    f"using median {median_dy:.1f}"
                                )
                                M_fix = np.eye(2, 3, dtype=np.float32)
                                M_fix[0, 2] = e["M"][0, 2]
                                M_fix[1, 2] = median_dy
                                e = _apply_corrected_M(e, M_fix, e.get("weight", 1.0) * 0.3)
                        else:
                            print(
                                f"[Stitch]   Edge {fi}→{fj}: dy={dy:.1f} kept "
                                f"(consensus {median_dy:.1f})"
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

        print(f"[Stitch] Starting AnimeStitchPipeline on {len(image_paths)} frames.")
        self._baselines = None

        # ── Stage 1: Load & trim ─────────────────────────────────────────────
        frames = _load_frames(image_paths)
        N = len(frames)
        if N < 2:
            raise ValueError("Need at least 2 valid frames to stitch.")
        print(f"[Stitch] Stage 1 complete: {N} frames loaded.")

        # ── Stage 2: Width normalisation ─────────────────────────────────────
        frames = _normalise_widths(frames)
        H, W = frames[0].shape[:2]
        print(f"[Stitch] Stage 2 complete: all frames at {W}×{H}.")

        # ── Stage 3: BaSiC photometric correction ────────────────────────────
        if self.use_basic:
            if self._basic is None:
                self._basic = BaSiCWrapper()
            frames, baselines = _apply_basic(frames, self._basic)
            self._baselines = baselines
            frames = _correct_vignetting(frames)
            print("[Stitch] Stage 3 complete: BaSiC + Vignette correction applied.")
        else:
            print("[Stitch] Stage 3 skipped (use_basic=False).")

        # ── Stage 4: Foreground masking ──────────────────────────────────────
        if self.use_birefnet and self._birefnet is None:
            self._birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(
            frames,
            self._birefnet,
            use_birefnet=self.use_birefnet,
        )
        if torch.cuda.is_available() and self._birefnet is not None:
            try:
                self._birefnet.offload()
            except Exception:
                pass
            self._birefnet = None
            torch.cuda.empty_cache()
        print(
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
                _gain = np.clip(_gain, 0.88, 1.14)
                if not np.allclose(_gain, 1.0, atol=0.01):
                    frames[_i] = np.clip(
                        frames[_i].astype(np.float32) * _gain, 0, 255
                    ).astype(np.uint8)
            print(
                f"[Stitch] Stage 4.5 complete: background photometric normalisation "
                f"({len(_valid_means)}/{N} frames had sufficient background)."
            )

        # ── Stage 5-6: Pairwise matching (+ skip-pair edges) ────────────────
        if self.use_loftr and self._loftr is None:
            self._loftr = LoFTRWrapper()
        edges = _pairwise_match(
            frames,
            bg_masks,
            loftr_wrapper=self._loftr,
            use_loftr=self.use_loftr,
            motion_model=self.motion_model,
        )

        edges = self._filter_edges(edges, image_paths, H, W, frames, bg_masks)

        if torch.cuda.is_available() and self._loftr is not None:
            try:
                self._loftr.offload()
            except Exception:
                pass
            torch.cuda.empty_cache()
            gc.collect()
            self._loftr = None
            torch.cuda.empty_cache()
        print(f"[Stitch] Stages 5-6 complete: {len(edges)} valid edges found.")
        if not edges:
            warnings.warn("[Stitch] No valid edges — falling back to scan stitch.")
            return _scan_stitch_fallback(frames, output_path)

        # ── Stage 7: Global bundle adjustment ────────────────────────────────
        use_affine_ba = getattr(self, "motion_model", "affine") == "affine"
        affines = _bundle_adjust_affine(edges, N, use_affine=use_affine_ba)
        print(
            f"[Stitch] Stage 7 complete: bundle adjustment done "
            f"(mode={'affine' if use_affine_ba else 'translation'})."
        )

        # ── Stage 8: ECC sub-pixel refinement ───────────────────────────────
        if self.use_ecc:
            affines = _ecc_refine(frames, affines, bg_masks)
            print("[Stitch] Stage 8 complete: ECC refinement done.")
        else:
            print("[Stitch] Stage 8 skipped (use_ecc=False).")

        # ── Stage 9: Canvas construction ────────────────────────────────────
        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        print(f"[Stitch] Stage 9: canvas size {canvas_w}×{canvas_h}.")
        if canvas_h <= 0 or canvas_w <= 0:
            raise RuntimeError("Computed canvas has zero size.")

        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        # ── Stage 10: Temporal renderer ─────────────────────────────────────
        canvas, valid_mask, warped_corr, warped_fgs = _render(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            renderer=self.renderer,
            baselines=self._baselines,
        )
        print("[Stitch] Stage 10 complete: temporal render done.")

        # ── Optional: MFSR super-resolution pass ─────────────────────────────
        if self.mfsr_mode:
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
                print("[Stitch]   MFSR refinement complete.")
            except Exception as e:
                print(
                    f"[Stitch]   MFSR refinement failed ({e}); keeping median canvas."
                )

        # ── Stage 11: Foreground composite ──────────────────────────────────
        if self.composite_fg and self.use_birefnet:
            canvas = _composite_foreground(
                [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks
            )
            print("[Stitch] Stage 11 complete: foreground composited.")

        # ── Stage 12: Remaining seam blend (handled inside _render). ────────

        # ── Stage 13: Morphological boundary crop ───────────────────────────
        canvas = _crop_to_valid(canvas, valid_mask)
        if getattr(self, "edge_crop", 0) > 0:
            ec = self.edge_crop
            if ec * 2 < canvas.shape[0] and ec * 2 < canvas.shape[1]:
                canvas = canvas[ec:-ec, ec:-ec]
        print("[Stitch] Stage 13 complete: boundary crop done.")

        # ── Save ─────────────────────────────────────────────────────────────
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out = Image.fromarray(rgb)
        out.save(output_path)
        gc.collect()
        print(f"[Stitch] Done. Saved to '{output_path}'.")
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
