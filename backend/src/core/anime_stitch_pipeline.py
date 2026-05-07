"""
anime_stitch_pipeline.py
========================
Multi-stage anime panorama stitching pipeline.

Designed to be called from ImageMerger.perfect_stitch as a drop-in replacement.
Can also be used standalone::

    from backend.src.core.anime_stitch_pipeline import AnimeStitchPipeline
    result_pil = AnimeStitchPipeline().run(image_paths, output_path)

Pipeline stages
---------------
1.  Load & dark-border trim
2.  Width normalisation (Lanczos)
3.  BaSiC photometric correction  — removes broadcast dimming, vignettes
4.  BiRefNet foreground masking   — anime-tuned ToonOut weights
5.  Pairwise LoFTR matching       — background-only, 4-DoF affine-partial
6.  Parallel-pan detection        — skip-pair edges (i→i+2, i→i+3)
7.  Global bundle adjustment      — Levenberg-Marquardt over affine graph
8.  ECC sub-pixel refinement      — area-based, mask-aware
9.  Canvas construction           — float64 accumulator
10. Temporal median render        — Overmix-style; suppresses MPEG noise &
                                    moving foreground via per-pixel median
11. Foreground composite          — single best frame's character pasted back
12. Multi-band (Laplacian) seam   — final quality pass over any remaining seams
13. Morphological boundary crop   — largest inscribed non-black rectangle
14. Save & return

Fallback chain
--------------
If LoFTR fails for a pair (< min_inliers or model unavailable):
  → Template matching on masked Y' channel
  → Phase correlation on high-pass filtered Y' (masked)
  → Identity (frames stacked with warning)

The pipeline is designed so that removing any optional dependency
(kornia, transformers) gracefully falls back rather than crashing.

References
----------
- Brown & Lowe, "Automatic Panoramic Image Stitching", IJCV 2007
- Spillerrec, "Stitching anime screenshots in overdrive", 2013
  https://spillerrec.dk/2013/02/
- ToonOut (Muratori & Seytre), arXiv:2509.06839, 2025
- EfficientLoFTR, CVPR 2024
"""

from __future__ import annotations

import os

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

import gc
import torch
import warnings
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from scipy.optimize import least_squares

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
    from backend.src.models.stitch_net.trainer import load_stitch_net
    from backend.src.models.stitch_net.model import AnimeStitchNet

    _STITCH_NET_OK = True
except ImportError:
    _STITCH_NET_OK = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LAPLACIAN_BANDS = 5  # Laplacian pyramid depth for multi-band blend
_ECC_MAX_ITER = 80  # ECC termination iterations
_ECC_EPS = 1e-4  # ECC termination epsilon
_ECC_PYRAMID_LEVELS = 4  # Gaussian pyramid levels for ECC
_MIN_LOFTR_INLIERS = 20  # Minimum MAGSAC++ inliers for a valid LoFTR pair
_MIN_TEMPLATE_SCORE = 0.55  # Minimum TM_CCORR_NORMED score for template match
_PC_CONF_THRESHOLD = 0.08  # Minimum phase-correlation response (shallow = noisy)
_CANVAS_MAX_DIM = 32768  # Hard cap on canvas size to avoid OOM
_MEDIAN_MIN_SAMPLES = 3  # Minimum valid samples per pixel for median render
_FOREGROUND_DILATION = 16  # BiRefNet mask dilation (safety margin around chars)
_FOREGROUND_EROSION = 8  # BiRefNet mask erosion (sharpens boundary)
_SMOOTHSTEP_BLEND_PX = 96  # Fallback blend height when seam is unavailable


# ---------------------------------------------------------------------------
# Standalone helper functions (no class state)
# ---------------------------------------------------------------------------


def _luma(bgr: np.ndarray) -> np.ndarray:
    """Return Y' channel (uint8 2-D) from a BGR uint8 image."""
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)[..., 0]


def _highpass(gray: np.ndarray, sigma: float = 3.0) -> np.ndarray:
    """Subtract Gaussian-blurred version to isolate high-frequency content."""
    blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
    hp = gray.astype(np.float32) - blurred.astype(np.float32)
    # Shift to [0,255] for phase correlation
    hp = hp - hp.min()
    hp = (hp / (hp.max() + 1e-6) * 255.0).astype(np.float32)
    return hp


def _trim_dark_border(arr: np.ndarray, pct: float = 0.20) -> np.ndarray:
    """
    Remove broadcast-safe dark bars (common in anime BDs cropped for TV).
    Trims rows/columns whose mean brightness is below `pct` of the overall median.
    """
    if arr.shape[0] < 8 or arr.shape[1] < 8:
        return arr
    gray = arr.mean(axis=2)
    row_m = gray.mean(axis=1)
    col_m = gray.mean(axis=0)
    med_r = float(np.median(row_m)) or 1.0
    med_c = float(np.median(col_m)) or 1.0
    thr_r = max(med_r * pct, 4.0)
    thr_c = max(med_c * pct, 4.0)

    top = next((y for y in range(len(row_m)) if row_m[y] >= thr_r), 0)
    bot = (
        next(
            (y for y in range(len(row_m) - 1, -1, -1) if row_m[y] >= thr_r),
            len(row_m) - 1,
        )
        + 1
    )
    left = next((x for x in range(len(col_m)) if col_m[x] >= thr_c), 0)
    right = (
        next(
            (x for x in range(len(col_m) - 1, -1, -1) if col_m[x] >= thr_c),
            len(col_m) - 1,
        )
        + 1
    )

    trimmed = arr[top:bot, left:right]
    return trimmed if trimmed.size > 0 else arr


def _laplacian_blend(
    a: np.ndarray,
    b: np.ndarray,
    mask_float: np.ndarray,
    bands: int = _LAPLACIAN_BANDS,
) -> np.ndarray:
    """
    Multi-band (Laplacian pyramid) blending.

    `a` is taken where mask_float = 1, `b` where mask_float = 0.
    Low frequencies blended broadly; high frequencies blended narrowly at seam.
    Superior to Poisson blending for cel-shaded anime (avoids color bleeding
    across hard cel boundaries).

    Parameters
    ----------
    a, b : (H, W, 3) uint8 BGR images.
    mask_float : (H, W) float32 in [0, 1].
    bands : pyramid depth.
    """
    mask = mask_float[:, :, np.newaxis].astype(np.float32)
    ga = [a.astype(np.float32)]
    gb = [b.astype(np.float32)]
    gm = [mask]
    for _ in range(bands - 1):
        ga.append(cv2.pyrDown(ga[-1]))
        gb.append(cv2.pyrDown(gb[-1]))
        gm.append(cv2.pyrDown(gm[-1]))

    la = [ga[-1]]
    lb = [gb[-1]]
    for k in range(len(ga) - 1, 0, -1):
        la.append(ga[k - 1] - cv2.pyrUp(ga[k], dstsize=ga[k - 1].shape[1::-1]))
        lb.append(gb[k - 1] - cv2.pyrUp(gb[k], dstsize=gb[k - 1].shape[1::-1]))

    blended = []
    for k in range(bands):
        m = gm[bands - 1 - k]
        if m.shape[:2] != la[k].shape[:2]:
            m = cv2.resize(m, (la[k].shape[1], la[k].shape[0]))
        if m.ndim == 2:
            m = m[:, :, np.newaxis]
        blended.append(la[k] * m + lb[k] * (1.0 - m))

    result = blended[0]
    for k in range(1, bands):
        result = cv2.pyrUp(result, dstsize=blended[k].shape[1::-1]) + blended[k]
    return np.clip(result, 0, 255).astype(np.uint8)


def _seam_dp(
    img1: np.ndarray,
    img2: np.ndarray,
    horizontal: bool = True,
) -> np.ndarray:
    """
    Dynamic-programming optimal seam between two images.
    Energy = colour diff + gradient diff.  Seam avoids high-contrast edges
    (anime line art), preferring flat cel-shaded regions.

    Parameters
    ----------
    horizontal : if True, the seam is horizontal (separates top/bottom);
                 if False, the seam is vertical (separates left/right).

    Returns
    -------
    path : int array of length W (horizontal) or H (vertical),
           giving the seam row per column (or column per row).
    """
    diff = cv2.absdiff(img1, img2).astype(np.float32).mean(axis=2)
    gx = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
    energy = diff + 0.5 * (np.abs(gx) + np.abs(gy))

    if not horizontal:
        energy = energy.T
    h, w = energy.shape

    M = energy.copy()
    for i in range(1, h):
        left = np.empty_like(M[i - 1]); left[0] = np.inf; left[1:] = M[i - 1, :-1]
        right = np.empty_like(M[i - 1]); right[-1] = np.inf; right[:-1] = M[i - 1, 1:]
        M[i] += np.minimum(M[i - 1], np.minimum(left, right))

    path = np.zeros(h, np.int32)
    j = int(np.argmin(M[h - 1]))
    path[h - 1] = j
    for i in range(h - 2, -1, -1):
        nbrs = [j]
        if j > 0:
            nbrs.append(j - 1)
        if j < w - 1:
            nbrs.append(j + 1)
        j = nbrs[int(np.argmin([M[i, c] for c in nbrs]))]
        path[i] = j

    return path  # horizontal=False: path is column-per-row (transposed)


def _largest_valid_rect(mask: np.ndarray) -> Tuple[int, int, int, int]:
    """
    Find the largest axis-aligned rectangle of valid (non-zero) pixels.

    Strategy
    --------
    Vertical pans produce a canvas that is valid everywhere except a
    narrow black border.  We exploit this with a two-step approach:

    1. Fast path: project the mask onto rows and columns.
       - Find the widest contiguous column band where ≥95% of rows are valid.
       - Find the tallest contiguous row band where ≥95% of columns are valid.
       - The intersection is returned immediately if it covers ≥40% of valid pixels.

    2. Histogram fallback on an aggressively downsampled (16×) mask.
       At 16× downsampling, a 3844×7372 canvas becomes 240×461 cells —
       110K iterations of the Python stack loop rather than 27M.

    Returns (x0, y0, x1, y1) — half-open column/row bounds.
    """
    h, w = mask.shape
    if h == 0 or w == 0:
        return (0, 0, w, h)

    binary = mask > 0  # bool (H, W)

    # ── Fast path ─────────────────────────────────────────────────────────────
    # row_valid_frac[r] = fraction of columns that are valid in row r
    row_frac = binary.mean(axis=1)  # (H,) float
    col_frac = binary.mean(axis=0)  # (W,) float

    def _longest_thresh_run(frac, thr=0.95):
        """Longest contiguous run where frac >= thr."""
        bools = frac >= thr
        best_s, best_l = 0, 0
        cs, cl = 0, 0
        for i, v in enumerate(bools):
            if v:
                if cl == 0:
                    cs = i
                cl += 1
                if cl > best_l:
                    best_l, best_s = cl, cs
            else:
                cl = 0
        return best_s, best_l

    r0, rlen = _longest_thresh_run(row_frac, 0.95)
    c0, clen = _longest_thresh_run(col_frac, 0.95)

    fast_area = rlen * clen
    valid_px = max(int(binary.sum()), 1)

    if fast_area >= 0.40 * valid_px:
        return (c0, r0, c0 + clen, r0 + rlen)

    # ── Histogram fallback at 16× downscaling ─────────────────────────────────
    DS = 16
    hs = max(h // DS, 1)
    ws = max(w // DS, 1)
    small = cv2.resize(
        binary.astype(np.uint8) * 255,
        (ws, hs),
        interpolation=cv2.INTER_NEAREST,
    )
    bin_s = (small > 0).astype(np.int32)
    heights = np.zeros(ws, np.int32)
    best = (0, 0, w, h)
    best_area = 0

    for row in range(hs):
        heights = np.where(bin_s[row], heights + 1, 0)
        stack: List[int] = []
        for col in range(ws + 1):
            cur_h = int(heights[col]) if col < ws else 0
            start = col
            while stack and int(heights[stack[-1]]) > cur_h:
                idx = stack.pop()
                hh = int(heights[idx])
                ww = col - (stack[-1] + 1 if stack else 0)
                area = hh * ww
                if area > best_area:
                    best_area = area
                    x0s = stack[-1] + 1 if stack else 0
                    y0s = row - hh + 1
                    best = (
                        min(x0s * DS, w),
                        min(y0s * DS, h),
                        min((x0s + ww) * DS, w),
                        min((y0s + hh) * DS, h),
                    )
                start = idx
            stack.append(start)
            if col < ws:
                heights[start] = cur_h

    return best  # (x0, y0, x1, y1)  half-open


# ---------------------------------------------------------------------------
# Bundle Adjustment
# ---------------------------------------------------------------------------


def _bundle_adjust_affine(
    edges: List[Dict],
    num_frames: int,
    iterations: int = 200,
) -> List[np.ndarray]:
    """
    Global Levenberg-Marquardt bundle adjustment for affine transforms.

    We use a strict translation-only BA (rotation/scale locked to identity)
    to eliminate 'fan' or 'spiraling' distortion.

    The function minimises:
        Σ || (p_i + t_i) - (p_j + t_j) ||²  for anchor points p

    Frame 0 is pinned at identity (zero translation).

    Parameters
    ----------
    edges : list of dicts with keys:
        'i', 'j'   — frame indices (i < j)
        'M'        — (2,3) float32 affine matrix mapping i → j (only translation is used)
        'pts_i'    — (K,2) float32 sample points in frame i coords
        'pts_j'    — (K,2) float32 matched points in frame j coords
        'weight'   — float, confidence weight
    num_frames : total number of frames (including frame 0).

    Returns
    -------
    List of (2, 3) float32 translation-only matrices, one per frame.
    Frame 0 is identity.
    """
    # x = [tx_0, ty_0, tx_1, ty_1, ..., tx_{N-1}, ty_{N-1}]  (translation only)
    x0 = np.zeros(num_frames * 2, np.float64)

    # Initial sequential guess using pairwise translations
    # Correct relation: t_j = t_i - t_raw (where pts_j = pts_i + t_raw)
    for f in range(1, num_frames):
        # Find edge (f-1) -> f if available
        for e in edges:
            if e["i"] == f - 1 and e["j"] == f:
                tx_raw = float(e["M"][0, 2])
                ty_raw = float(e["M"][1, 2])
                # t_f = t_{f-1} - t_{raw}
                x0[f * 2] = x0[(f - 1) * 2] - tx_raw
                x0[f * 2 + 1] = x0[(f - 1) * 2 + 1] - ty_raw
                break
            elif e["i"] == f and e["j"] == f - 1:
                tx_raw = float(e["M"][0, 2])
                ty_raw = float(e["M"][1, 2])
                # t_{f-1} = t_f - t_{raw} -> t_f = t_{f-1} + t_{raw}
                x0[f * 2] = x0[(f - 1) * 2] + tx_raw
                x0[f * 2 + 1] = x0[(f - 1) * 2 + 1] + ty_raw
                break

    def residuals(x: np.ndarray) -> np.ndarray:
        res = []
        for e in edges:
            i, j, w = e["i"], e["j"], float(e.get("weight", 1.0))
            ti = x[i * 2 : i * 2 + 2]
            tj = x[j * 2 : j * 2 + 2]

            pts_i = e["pts_i"].astype(np.float64)  # (K,2)
            pts_j = e["pts_j"].astype(np.float64)

            # Global positions: frame_i @ pt → pt + ti; frame_j → pt_j + tj
            # Enforcing translation-only, so rotation is identity
            diff = (pts_i + ti) - (pts_j + tj)  # residual in global coords
            res.extend((diff * w).flatten())

        # Anchor frame 0 at identity
        reg = 0.3
        res.append(reg * x[0])
        res.append(reg * x[1])
        return np.array(res, np.float64)

    result = least_squares(
        residuals,
        x0,
        method="trf",
        ftol=1e-5,
        xtol=1e-5,
        gtol=1e-5,
        max_nfev=iterations * num_frames,
        verbose=0,
    )
    x_opt = result.x

    # Build (2,3) affine matrices from optimised translations.
    # Rotation and scale are strictly locked to identity to prevent distortion.
    out: List[np.ndarray] = [np.eye(2, 3, dtype=np.float32)]
    for f in range(1, num_frames):
        M = np.eye(2, 3, dtype=np.float32)
        M[0, 2] = float(x_opt[f * 2])
        M[1, 2] = float(x_opt[f * 2 + 1])
        out.append(M)
    return out


# ---------------------------------------------------------------------------
# Main Pipeline Class
# ---------------------------------------------------------------------------


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
        use_ecc: bool = True,
        renderer: str = "median",  # 'median' | 'first' | 'blend'
        composite_fg: bool = True,
        laplacian_bands: int = _LAPLACIAN_BANDS,
        stitch_net_ckpt: str = "",  # path to AnimeStitchNet checkpoint
    ):
        self.use_basic = use_basic and _BASIC_OK
        self.use_birefnet = use_birefnet and _BIREFNET_OK
        self.use_loftr = use_loftr and _LOFTR_OK
        self.use_ecc = use_ecc
        self.renderer = renderer
        self.composite_fg = composite_fg
        self.bands = laplacian_bands
        self.stitch_net_ckpt = stitch_net_ckpt

        # Lazy-loaded model instances (only allocated if the flag is True)
        self._basic: Optional[BaSiCWrapper] = None
        self._baselines: Optional[List[float]] = None  # per-frame dimming scalars from BaSiC
        self._birefnet: Optional[BiRefNetWrapper] = None
        self._loftr: Optional[LoFTRWrapper] = None
        self._stitch_net: Optional["AnimeStitchNet"] = None  # trained DL matcher

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
        print(f"[Stitch] Starting AnimeStitchPipeline on {len(image_paths)} frames.")
        self._baselines = None  # reset per-run; populated by _apply_basic if use_basic=True

        # ── Stage 1: Load & trim ─────────────────────────────────────────────
        frames = self._load_frames(image_paths)
        N = len(frames)
        if N < 2:
            raise ValueError("Need at least 2 valid frames to stitch.")
        print(f"[Stitch] Stage 1 complete: {N} frames loaded.")

        # ── Stage 2: Width normalisation ─────────────────────────────────────
        frames = self._normalise_widths(frames)
        H, W = frames[0].shape[:2]
        print(f"[Stitch] Stage 2 complete: all frames at {W}×{H}.")

        # ── Stage 3: BaSiC photometric correction ────────────────────────────
        if self.use_basic:
            frames = self._apply_basic(frames)
            print("[Stitch] Stage 3 complete: BaSiC correction applied.")
        else:
            print("[Stitch] Stage 3 skipped (use_basic=False).")

        # ── Stage 4: Foreground masking ──────────────────────────────────────
        bg_masks = self._compute_fg_masks(frames)
        if torch.cuda.is_available():
            self._birefnet.offload()
            self._birefnet = None
            torch.cuda.empty_cache()  # list of (H,W) uint8, 255=bg
        print(
            f"[Stitch] Stage 4 complete: foreground masks ready "
            f"({'BiRefNet' if self.use_birefnet else 'None'})."
        )

        # ── Stage 5-6: Pairwise LoFTR matching (+ skip-pair edges) ──────────
        edges = self._pairwise_match(frames, bg_masks)
        if torch.cuda.is_available():
            self._loftr.offload()
            torch.cuda.empty_cache()
            gc.collect()
            self._loftr = None
            torch.cuda.empty_cache()
        print(f"[Stitch] Stages 5-6 complete: {len(edges)} valid edges found.")
        if not edges:
            warnings.warn("[Stitch] No valid edges — falling back to scan stitch.")
            return self._scan_stitch_fallback(frames, output_path)

        # ── Stage 7: Global bundle adjustment ───────────────────────────────
        affines = _bundle_adjust_affine(edges, N)
        print("[Stitch] Stage 7 complete: bundle adjustment done.")

        # ── Stage 8: ECC sub-pixel refinement ───────────────────────────────
        if self.use_ecc:
            affines = self._ecc_refine(frames, affines, bg_masks)
            print("[Stitch] Stage 8 complete: ECC refinement done.")
        else:
            print("[Stitch] Stage 8 skipped (use_ecc=False).")

        # ── Stage 9: Canvas construction ────────────────────────────────────
        canvas_h, canvas_w, T_global = self._compute_canvas(frames, affines)
        print(f"[Stitch] Stage 9: canvas size {canvas_w}×{canvas_h}.")
        if canvas_h <= 0 or canvas_w <= 0:
            raise RuntimeError("Computed canvas has zero size.")

        # Incorporate global offset into all affines
        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        # ── Stage 10: Temporal renderer ─────────────────────────────────────
        canvas, valid_mask, warped_corr, warped_fgs = self._render(
            frames, affines, bg_masks, canvas_h, canvas_w
        )
        print("[Stitch] Stage 10 complete: temporal render done.")

        # ── Stage 11: Foreground composite ──────────────────────────────────
        if self.composite_fg and self.use_birefnet:
            canvas = self._composite_foreground(
                [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks
            )
            print("[Stitch] Stage 11 complete: foreground composited.")

        # ── Stage 12: Remaining seam blend (blend renderer only) ────────────
        # The median renderer already handles seams implicitly;
        # for 'blend' mode a sequential Laplacian pass was done inside _render.
        # No additional pass needed here.

        # ── Stage 13: Morphological boundary crop ───────────────────────────
        canvas = self._crop_to_valid(canvas, valid_mask)
        print("[Stitch] Stage 13 complete: boundary crop done.")

        # ── Save ─────────────────────────────────────────────────────────────
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        out = Image.fromarray(rgb)
        out.save(output_path)
        gc.collect()
        print(f"[Stitch] Done. Saved to '{output_path}'.")
        return out

    # ---------------------------------------------------------------- stages

    # Stage 1
    def _load_frames(self, paths: List[str]) -> List[np.ndarray]:
        frames = []
        for p in paths:
            img = cv2.imread(p)
            if img is None:
                print(f"[Stitch] Warning: could not read '{p}' — skipping.")
                continue
            img = _trim_dark_border(img)
            frames.append(img)
        return frames

    # Stage 2
    @staticmethod
    def _normalise_widths(frames: List[np.ndarray]) -> List[np.ndarray]:
        target_w = frames[0].shape[1]
        out = []
        for img in frames:
            h, w = img.shape[:2]
            if w != target_w:
                nh = int(round(h * target_w / w))
                img = cv2.resize(img, (target_w, nh), interpolation=cv2.INTER_LANCZOS4)
            out.append(img)
        return out

    # Stage 3
    def _apply_basic(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        """
        Apply BaSiC spatial flat-field correction only.

        For stitching we deliberately do NOT apply the per-frame dimming
        baseline (b_i) correction.  BaSiC's b_i makes each frame's mean
        brightness equal to the stack median, which destroys the natural
        inter-frame brightness continuity and causes colour discontinuities
        at seam boundaries.  The spatial flat-field F (vignette/shading)
        is the only correction we apply here; inter-frame colour differences
        are handled later by histogram matching inside _render_median.
        """
        if self._basic is None:
            self._basic = BaSiCWrapper()

        print("[Stitch]   Fitting BaSiC flat-field (spatial correction only)…")

        if hasattr(self._basic, "fit"):
            # New API: fit to get flat_field, then apply WITHOUT per-frame b_i
            flat, dark, baselines = self._basic.fit(frames, luma_only=True)
            self._baselines = baselines.tolist()
            dim_frames = [i for i, bi in enumerate(baselines) if bi < 0.75]
            if dim_frames:
                print(
                    f"[Stitch]   Broadcast-dimming detected in frames: {dim_frames} "
                    f"(b_i correction deferred to renderer)"
                )
            # Apply flat-field only (b=1.0 → no per-frame brightness change)
            return [
                self._basic.apply_correction(img, baseline_override=1.0)
                for img in frames
            ]

        # Legacy fallback
        if hasattr(self._basic, "process_batch"):
            return self._basic.process_batch(frames)
        self._basic.estimate_profiles(frames)
        return [self._basic.apply_correction(img) for img in frames]

    # Stage 4
    def _compute_fg_masks(self, frames: List[np.ndarray]) -> List[Optional[np.ndarray]]:
        """Returns list of background masks (255 = safe background, 0 = character)."""
        if not self.use_birefnet:
            return [None] * len(frames)

        if self._birefnet is None:
            self._birefnet = BiRefNetWrapper()

        # Detect which API version is loaded
        has_new_api = hasattr(self._birefnet, "get_background_mask")

        masks = []
        for i, img in enumerate(frames):
            try:
                if has_new_api:
                    # New API: returns 255=background, 0=foreground, with dilation/erosion
                    bg = self._birefnet.get_background_mask(
                        img,
                        dilate_px=_FOREGROUND_DILATION,
                        erode_px=_FOREGROUND_EROSION,
                    )
                else:
                    # Legacy API: get_mask returns 255=foreground; invert + dilate manually
                    fg = self._birefnet.get_mask(img)
                    bg = cv2.bitwise_not(fg)
                    if _FOREGROUND_DILATION > 0:
                        k = cv2.getStructuringElement(
                            cv2.MORPH_ELLIPSE,
                            (
                                2 * _FOREGROUND_DILATION + 1,
                                2 * _FOREGROUND_DILATION + 1,
                            ),
                        )
                        # Dilate the foreground mask (shrinks the safe background zone)
                        fg_dilated = cv2.dilate(fg, k)
                        bg = cv2.bitwise_not(fg_dilated)
                masks.append(bg)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
            except Exception as e:
                print(f"[Stitch]   BiRefNet failed on frame {i}: {e}")
                masks.append(None)
        return masks

    # Stages 5-6
    def _pairwise_match(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[Dict]:
        """
        Build pairwise correspondence edges using LoFTR → template match → PC fallback.
        Adds consecutive (i→i+1) plus skip-pair (i→i+2, i→i+3) edges.
        """
        N = len(frames)
        H, W = frames[0].shape[:2]

        if self.use_loftr and self._loftr is None:
            self._loftr = LoFTRWrapper()

        # Build list of (i, j) pairs to try
        pairs: List[Tuple[int, int]] = []
        for i in range(N - 1):
            pairs.append((i, i + 1))
        for i in range(N - 2):
            pairs.append((i, i + 2))  # skip-1
        for i in range(N - 3):
            pairs.append((i, i + 3))  # skip-2

        edges: List[Dict] = []
        for idx, (i, j) in enumerate(pairs):
            edge = self._match_pair(frames, bg_masks, i, j, H, W)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
            if edge is not None:
                edges.append(edge)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        return edges

    def _match_pair(
        self,
        frames: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        i: int,
        j: int,
        H: int,
        W: int,
    ) -> Optional[Dict]:
        """
        Try to match frame i to frame j.  Returns edge dict or None.
        """
        img_i, img_j = frames[i], frames[j]
        m_i = bg_masks[i]  # 255 = background
        m_j = bg_masks[j]

        M: Optional[np.ndarray] = None
        mean_conf = 0.0
        actual_pts_i: Optional[np.ndarray] = None
        actual_pts_j: Optional[np.ndarray] = None

        # ── Attempt 0: Trained AnimeStitchNet (fastest, if checkpoint provided)
        if self.stitch_net_ckpt and _STITCH_NET_OK:
            try:
                import math
                import torch.nn.functional as F_nn

                if self._stitch_net is None:
                    self._stitch_net = load_stitch_net(self.stitch_net_ckpt)
                net = self._stitch_net
                pH_nn, pW_nn = img_i.shape[:2]

                def _to_tensor(bgr):
                    y = (
                        cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)[..., 0].astype("float32")
                        / 255.0
                    )
                    return torch.from_numpy(y).unsqueeze(0).unsqueeze(0)

                ti = _to_tensor(img_i)
                tj = _to_tensor(img_j)
                dev = next(net.parameters()).device
                with torch.no_grad():
                    params = net(ti.to(dev), tj.to(dev)).cpu()
                from backend.src.models.stitch_net.model import AnimeStitchNet as _ASN

                M_t = _ASN.params_to_affine(params, pH_nn, pW_nn).squeeze(0)
                M = M_t.numpy().astype("float32")
                mean_conf = 0.75  # fixed confidence for net predictions
                print(
                    f"[Stitch]   {i}→{j}: StitchNet dx={M[0, 2]:.1f} dy={M[1, 2]:.1f}"
                )
            except Exception as e:
                print(f"[Stitch]   {i}→{j}: StitchNet error: {e}")
                M = None

        # ── Attempt 1: LoFTR + MAGSAC++ (4-DoF affine-partial) ───────────
        if self.use_loftr and M is None:
            try:
                if hasattr(self._loftr, "match_masked"):
                    # New API: match_masked → RANSAC to capture inlier points
                    pts1_m, pts2_m, conf_m = self._loftr.match_masked(
                        img_i, img_j, mask1=m_i, mask2=m_j
                    )
                    if len(pts1_m) >= _MIN_LOFTR_INLIERS:
                        M_raw, inliers = cv2.estimateAffinePartial2D(
                            pts1_m,
                            pts2_m,
                            method=cv2.RANSAC,
                            ransacReprojThreshold=2.0,
                            confidence=0.999,
                            maxIters=10_000,
                        )
                        if M_raw is not None and inliers is not None:
                            inl_mask = inliers.ravel().astype(bool)
                            if inl_mask.sum() >= _MIN_LOFTR_INLIERS:
                                M = M_raw.astype(np.float32)
                                mean_conf = float(conf_m[inl_mask].mean())
                                actual_pts_i = pts1_m[inl_mask]
                                actual_pts_j = pts2_m[inl_mask]
                else:
                    # Legacy API: match() → filter → estimateAffinePartial2D
                    pts1, pts2, conf = self._loftr.match(img_i, img_j)
                    if len(pts1) >= 4:
                        # Filter by background mask if available
                        keep = np.ones(len(pts1), dtype=bool)
                        if m_i is not None:
                            h_i, w_i = m_i.shape[:2]
                            ix = np.clip(pts1[:, 0].astype(int), 0, w_i - 1)
                            iy = np.clip(pts1[:, 1].astype(int), 0, h_i - 1)
                            keep &= m_i[iy, ix] > 0
                        if m_j is not None:
                            h_j, w_j = m_j.shape[:2]
                            jx = np.clip(pts2[:, 0].astype(int), 0, w_j - 1)
                            jy = np.clip(pts2[:, 1].astype(int), 0, h_j - 1)
                            keep &= m_j[jy, jx] > 0
                        pts1_f, pts2_f, conf_f = pts1[keep], pts2[keep], conf[keep]
                        if len(pts1_f) >= _MIN_LOFTR_INLIERS:
                            M_raw, inliers = cv2.estimateAffinePartial2D(
                                pts1_f,
                                pts2_f,
                                method=cv2.RANSAC,
                                ransacReprojThreshold=3.0,
                                confidence=0.999,
                            )
                            if M_raw is not None and inliers is not None:
                                inl_mask = inliers.ravel().astype(bool)
                                if inl_mask.sum() >= _MIN_LOFTR_INLIERS:
                                    M = M_raw.astype(np.float32)
                                    mean_conf = float(conf_f[inl_mask].mean())
                                    actual_pts_i = pts1_f[inl_mask]
                                    actual_pts_j = pts2_f[inl_mask]
                if M is not None:
                    print(
                        f"[Stitch]   {i}→{j}: LoFTR "
                        f"dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} "
                        f"conf={mean_conf:.3f}"
                    )
            except Exception as e:
                print(f"[Stitch]   {i}→{j}: LoFTR error: {e}")
                M = None

        # ── Attempt 2: Template matching on masked Y' ─────────────────────
        if M is None:
            M, mean_conf = self._template_match(img_i, img_j, m_i, m_j, H)
            if M is not None:
                print(
                    f"[Stitch]   {i}→{j}: TemplateMatch "
                    f"dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
                )

        # ── Attempt 3: Phase correlation on high-pass Y' ──────────────────
        if M is None:
            M, mean_conf = self._phase_correlate(img_i, img_j, m_i, m_j)
            if M is not None:
                print(
                    f"[Stitch]   {i}→{j}: PhaseCorr "
                    f"dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} "
                    f"conf={mean_conf:.3f}"
                )

        if M is None:
            print(f"[Stitch]   {i}→{j}: all methods failed — skipping edge.")
            return None

        # For a translation-only pipeline, we enforce identity rotation/scale here
        # so that pts_j is consistent with the rigid model used in BA and rendering.
        M_transl = np.eye(2, 3, dtype=np.float32)
        M_transl[0, 2] = M[0, 2]
        M_transl[1, 2] = M[1, 2]
        M = M_transl

        # Build anchor points for the BA residuals
        if actual_pts_i is not None and actual_pts_j is not None:
            pts_i = actual_pts_i
            pts_j = actual_pts_j
        else:
            pts_i = self._sample_bg_points(m_i, H, W, n=200)
            pts_j = pts_i + M[:2, 2]

        return {
            "i": i,
            "j": j,
            "M": M,
            "pts_i": pts_i,
            "pts_j": pts_j,
            "weight": mean_conf,
        }

    @staticmethod
    def _template_match(
        img_i: np.ndarray,
        img_j: np.ndarray,
        m_i: Optional[np.ndarray],
        m_j: Optional[np.ndarray],
        H: int,
        slice_h: int = 192,
        max_search_frac: float = 0.95,
    ) -> Tuple[Optional[np.ndarray], float]:
        """
        Robust template match: find where the bottom of frame i appears in frame j.

        Improvements over the naive single-strip approach
        --------------------------------------------------
        • Multi-strip voting: uses 3 horizontal strips from the bottom of frame i
          and picks the best match by confidence-weighted median.  Reduces risk of
          a single low-texture strip winning.
        • Full-height search: searches up to max_search_frac × H rows into frame j
          instead of a hard 1500px cap, so large overlaps are handled correctly.
        • Horizontal offset: returns both dx and dy — cv2.matchTemplate searches
          across the full width, so the best-match column directly gives dx.
        • Correct dy formula: dy = y_match - (H - slice_h)
          i.e. the bottom strip of frame i (which starts at row H-slice_h in frame i)
          was found at row y_match in frame j.  The signed offset from frame i to
          frame j is therefore dy = y_match - (H - slice_h), which is ≤ 0 for
          upward panning (frame j is below frame i).
        • Confidence sanity check: rejects matches near the ROI boundary (may be
          artefacts of template padding) and matches with score < threshold.
        """
        g_i = _luma(img_i)  # float32 (H, W)
        g_j = _luma(img_j)

        W = g_i.shape[1]
        search_h = max(slice_h + 4, int(H * max_search_frac))

        # Three strip starting rows (bottom quarter of frame i)
        # Wider spacing → more robust to local texture failure
        strip_starts = [
            H - slice_h,  # bottom strip
            H - slice_h - slice_h // 2,  # mid strip
            H - slice_h - slice_h,  # upper strip (if it fits)
        ]
        strip_starts = [s for s in strip_starts if s >= 0 and s + slice_h <= H]

        best_dy = None
        best_dx = 0.0
        best_conf = 0.0

        roi = g_j[:search_h, :]  # region in frame j to search

        for strip_y in strip_starts:
            tmpl = g_i[strip_y : strip_y + slice_h, :].copy()

            # Background mask for this strip
            if m_i is not None:
                mask_strip = m_i[strip_y : strip_y + slice_h, :]
                # Skip strip if almost entirely foreground
                if mask_strip.mean() < 15:
                    continue
            else:
                mask_strip = None

            # Template must have enough texture to be distinctive
            if tmpl.std() < 2.0:
                continue

            # Ensure ROI is tall enough to fit the template
            if roi.shape[0] < slice_h:
                continue

            try:
                if mask_strip is not None:
                    res = cv2.matchTemplate(
                        roi, tmpl, cv2.TM_CCORR_NORMED, mask=mask_strip
                    )
                else:
                    res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCORR_NORMED)
            except cv2.error:
                try:
                    res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCORR_NORMED)
                except cv2.error:
                    continue

            _, v, _, loc = cv2.minMaxLoc(res)
            if v < _MIN_TEMPLATE_SCORE:
                continue

            # Reject match if it is at the very edge of the ROI (boundary artefact)
            ry, rx = loc[1], loc[0]
            if ry == 0 or ry >= res.shape[0] - 1:
                continue

            # Parabolic sub-pixel refinement (y axis)
            ry_sub = float(ry)
            d = 2 * res[ry, rx] - res[ry - 1, rx] - res[ry + 1, rx]
            if abs(d) > 1e-7:
                ry_sub -= (res[ry + 1, rx] - res[ry - 1, rx]) / (2.0 * d)

            # Sub-pixel refinement (x axis)
            rx_sub = float(rx)
            if 0 < rx < res.shape[1] - 1:
                d2 = 2 * res[ry, rx] - res[ry, rx - 1] - res[ry, rx + 1]
                if abs(d2) > 1e-7:
                    rx_sub -= (res[ry, rx + 1] - res[ry, rx - 1]) / (2.0 * d2)

            # dy: how much frame j is shifted vertically relative to frame i
            # The strip starting at `strip_y` in frame i was found at `ry_sub` in frame j.
            # So the top of frame j is at position (strip_y - ry_sub) in frame-i coords.
            # The translation from frame i origin to frame j origin is therefore:
            #   dy = ry_sub - strip_y      (negative = frame j is below frame i)
            dy_candidate = ry_sub - strip_y

            # dx: horizontal offset (positive = frame j shifted right)
            dx_candidate = (
                rx_sub  # match col in frame j minus 0 (template is full-width)
            )

            if v > best_conf:
                best_conf = v
                best_dy = dy_candidate
                best_dx = dx_candidate

        if best_dy is None:
            return None, 0.0

        M = np.array([[1.0, 0.0, best_dx], [0.0, 1.0, best_dy]], np.float32)
        return M, float(best_conf)

    @staticmethod
    def _phase_correlate(
        img_i: np.ndarray,
        img_j: np.ndarray,
        m_i: Optional[np.ndarray],
        m_j: Optional[np.ndarray],
    ) -> Tuple[Optional[np.ndarray], float]:
        """
        Phase correlation on high-pass filtered masked Y' channels.
        Returns (2,3) affine-partial M or None.
        """
        g_i = _highpass(_luma(img_i)).astype(np.float32)
        g_j = _highpass(_luma(img_j)).astype(np.float32)

        # Zero out foreground pixels to avoid character-relative drift
        if m_i is not None:
            g_i[m_i == 0] = 0.0
        if m_j is not None:
            g_j[m_j == 0] = 0.0

        try:
            hann = cv2.createHanningWindow(g_i.shape[::-1], cv2.CV_32F)
            shift, response = cv2.phaseCorrelate(g_i, g_j, hann)
        except Exception:
            return None, 0.0

        if response < _PC_CONF_THRESHOLD:
            return None, 0.0

        dx, dy = float(shift[0]), float(shift[1])
        M = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
        return M, float(response)

    @staticmethod
    def _sample_bg_points(
        mask: Optional[np.ndarray], H: int, W: int, n: int = 200
    ) -> np.ndarray:
        """Sample up to n (x,y) pixel coordinates from the background mask."""
        if mask is None:
            ys = np.random.randint(0, H, n)
            xs = np.random.randint(0, W, n)
        else:
            ys_bg, xs_bg = np.where(mask > 0)
            if len(ys_bg) == 0:
                ys = np.random.randint(0, H, n)
                xs = np.random.randint(0, W, n)
            else:
                idx = np.random.choice(len(ys_bg), min(n, len(ys_bg)), replace=False)
                ys, xs = ys_bg[idx], xs_bg[idx]
        return np.stack([xs, ys], axis=1).astype(np.float32)

    # Stage 8
    def _ecc_refine(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
    ) -> List[np.ndarray]:
        """
        Sub-pixel refinement of each frame's affine using ECC maximisation.

        Motion model choice
        -------------------
        MOTION_AFFINE (6 DoF) is overpowered for pure panning shots and lets
        ECC drift in x when motion is predominantly vertical.  We use
        MOTION_TRANSLATION (2 DoF) instead, which is sufficient for anime pans
        and keeps the optimisation well-conditioned.

        Safety clamp
        ------------
        After ECC we reject any correction that moves dx or dy more than
        _ECC_MAX_DRIFT pixels away from the bundle-adjusted starting point,
        falling back to the BA result.  This prevents ECC from diverging on
        low-texture frames.
        """
        _ECC_MAX_DRIFT = 80.0  # max px ECC is allowed to correct in each axis

        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            _ECC_MAX_ITER,
            _ECC_EPS,
        )
        refined = [affines[0].copy()]

        for i in range(1, len(frames)):
            M_i = affines[i].copy()  # global t_i
            M_prev = affines[i - 1].copy()  # global t_{i-1}

            ref_img = _luma(frames[i - 1])
            src_img = _luma(frames[i])
            ecc_mask = bg_masks[i - 1] if bg_masks[i - 1] is not None else None

            # Initialise ECC with the relative translation from i-1 to i
            # Relation: p_i + t_i = p_{i-1} + t_{i-1} -> p_i = p_{i-1} + (t_{i-1} - t_i)
            # So the warp from ref (i-1) to src (i) is t_{i-1} - t_i
            tx_rel_init = M_prev[0, 2] - M_i[0, 2]
            ty_rel_init = M_prev[1, 2] - M_i[1, 2]

            M_rel = np.eye(2, 3, dtype=np.float32)
            M_rel[0, 2] = tx_rel_init
            M_rel[1, 2] = ty_rel_init

            try:
                M_cur = M_rel.copy()
                for lvl in range(_ECC_PYRAMID_LEVELS - 1, -1, -1):
                    scale = 2**lvl
                    r_s = cv2.resize(
                        ref_img,
                        (ref_img.shape[1] // scale, ref_img.shape[0] // scale),
                        interpolation=cv2.INTER_AREA,
                    )
                    s_s = cv2.resize(
                        src_img,
                        (src_img.shape[1] // scale, src_img.shape[0] // scale),
                        interpolation=cv2.INTER_AREA,
                    )
                    M_s = M_cur.copy()
                    M_s[0, 2] /= scale
                    M_s[1, 2] /= scale

                    ecc_m_s = None
                    if ecc_mask is not None:
                        ecc_m_s = cv2.resize(
                            ecc_mask,
                            (ecc_mask.shape[1] // scale, ecc_mask.shape[0] // scale),
                            interpolation=cv2.INTER_NEAREST,
                        )

                    try:
                        _, M_s = cv2.findTransformECC(
                            r_s,
                            s_s,
                            M_s,
                            cv2.MOTION_TRANSLATION,
                            criteria,
                            ecc_m_s,
                            gaussFiltSize=5,
                        )
                        M_s[0, 2] *= scale
                        M_s[1, 2] *= scale
                        M_cur = M_s
                    except cv2.error:
                        break

                # Refined relative translation
                tx_rel_ec, ty_rel_ec = M_cur[0, 2], M_cur[1, 2]

                # Update global translation: t_i = t_{i-1} - t_{rel_ecc}
                tx_i_new = M_prev[0, 2] - tx_rel_ec
                ty_i_new = M_prev[1, 2] - ty_rel_ec

                # Safety clamp: reject if ECC moves t_i too far from BA start
                if (
                    abs(tx_i_new - M_i[0, 2]) > _ECC_MAX_DRIFT
                    or abs(ty_i_new - M_i[1, 2]) > _ECC_MAX_DRIFT
                ):
                    print(
                        f"[Stitch]   ECC frame {i}: correction clamped; keeping BA result."
                    )
                    refined.append(M_i)
                    continue

                M_out = M_i.copy()
                M_out[0, 2] = tx_i_new
                M_out[1, 2] = ty_i_new
                refined.append(M_out)
                print(
                    f"[Stitch]   ECC frame {i}: refined global dx={M_out[0, 2]:.2f} dy={M_out[1, 2]:.2f}"
                )

            except Exception as e:
                print(f"[Stitch]   ECC frame {i} failed ({e}); keeping BA result.")
                refined.append(M_i)

        return refined

    # Stage 9
    @staticmethod
    def _compute_canvas(
        frames: List[np.ndarray],
        affines: List[np.ndarray],
    ) -> Tuple[int, int, np.ndarray]:
        """
        Compute canvas dimensions and the global translation offset T_global
        that maps all warped corners into positive coordinates.

        Returns (canvas_h, canvas_w, T_global) where T_global is a (2,) array
        of (tx, ty) offsets to add to every affine's translation column.
        """
        all_corners = []
        for i, img in enumerate(frames):
            h, w = img.shape[:2]
            M = affines[i]
            corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
            # Apply 2×3 affine
            warped = (M[:2, :2] @ corners.T + M[:2, 2:3]).T
            all_corners.append(warped)

        all_corners = np.vstack(all_corners)
        min_xy = all_corners.min(axis=0)
        max_xy = all_corners.max(axis=0)

        T_global = -min_xy
        canvas_w = int(np.ceil(max_xy[0] - min_xy[0]))
        canvas_h = int(np.ceil(max_xy[1] - min_xy[1]))

        canvas_w = min(canvas_w, _CANVAS_MAX_DIM)
        canvas_h = min(canvas_h, _CANVAS_MAX_DIM)
        return canvas_h, canvas_w, T_global

    # Stage 10
    def _render(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        canvas_h: int,
        canvas_w: int,
    ) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
        """
        Dispatcher for different rendering modes.
        """
        if self.renderer == "median":
            return self._render_median(
                frames, affines, bg_masks, canvas_h, canvas_w,
                _baselines=self._baselines,
            )
        elif self.renderer == "first":
            c, v = self._render_first(frames, affines, canvas_h, canvas_w)
            return c, v, [], []
        else:
            # "blend" or default uses Laplacian
            return self._render_laplacian(frames, affines, bg_masks, canvas_h, canvas_w)

    def _render_median(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        H: int,
        W: int,
        _baselines: Optional[List[float]] = None,
        _skip_anim: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
        """
        Memory-efficient and FAST Temporal Median Render.
        Avoids float32 conversion and nanmedian where possible.
        """
        import numpy as np
        import cv2
        import warnings

        N = len(frames)
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        valid_mask = np.zeros((H, W), dtype=np.uint8)

        # Determine chunk size. We want to keep stack size < 1GB
        # N * chunk_h * W * 3 bytes (uint8)
        chunk_size = max(1, min(1024, (1024 * 1024 * 1024) // (N * W * 3 + 1)))

        print(f"[Stitch]   Rendering {N} frames in chunks of {chunk_size}px height...")

        for y0 in range(0, H, chunk_size):
            y1 = min(y0 + chunk_size, H)
            ch = y1 - y0

            # (N, ch, W, 3)
            stack = np.zeros((N, ch, W, 3), dtype=np.uint8)
            # (N, ch, W)
            masks = np.zeros((N, ch, W), dtype=bool)

            for i in range(N):
                M_strip = affines[i].copy()
                M_strip[1, 2] -= y0
                w_strip = cv2.warpAffine(
                    frames[i], M_strip, (W, ch), flags=cv2.INTER_LINEAR
                )
                if _baselines is not None:
                    b_i = float(_baselines[i])
                    if b_i < 0.95:
                        w_strip = np.clip(
                            w_strip.astype(np.float32) / max(b_i, 1e-4), 0, 255
                        ).astype(np.uint8)
                stack[i] = w_strip
                masks[i] = w_strip.max(axis=2) > 0

            # For each pixel, if count > 0, compute median of valid samples
            # This is still the bottleneck. We can optimize by only computing where masks.sum > 0
            # and using a faster median for common cases (N=1, N=2, N=3)

            # (ch, W)
            count = masks.sum(axis=0)

            # Case 1: pixels with exactly 1 sample (Very common in panoramas)
            m1 = count == 1
            if m1.any():
                # stack is (N, ch, W, 3). We want to pick the only valid one.
                # Since count is 1, masks has only one True per (y,x)
                idx1 = masks[:, m1].argmax(axis=0)  # (num_m1,)
                # stack[:, m1] is (N, num_m1, 3)
                # We need to take stack[idx1[j], j, :]
                # This is tricky with advanced indexing.
                canvas_strip = canvas[y0:y1]
                # Flat indexing for speed
                s_flat = stack.reshape(N, -1, 3)
                m1_flat = m1.flatten()
                canvas_strip.reshape(-1, 3)[m1_flat] = s_flat[
                    idx1, np.arange(len(idx1))
                ]

            # Case 2: pixels with > 1 samples (Where we actually need median)
            m_gt1 = count > 1
            if m_gt1.any():
                canvas_strip = canvas[y0:y1]
                # We use a masked median approach.
                # To avoid nanmedian, we can use a loop or partition on a slice.
                # For anime, N is usually small (e.g. 5-20 in overlap),
                # so we can use np.sort or np.partition.

                # Filter stack to only where m_gt1
                # stack_gt1 is (N, num_gt1, 3)
                s_gt1 = stack.reshape(N, -1, 3)[:, m_gt1.flatten(), :]
                masks_gt1 = masks.reshape(N, -1)[:, m_gt1.flatten()]

                # For each pixel in s_gt1, we need median of valid entries.
                # This is STILL slow if done in a loop.
                # Optimized approach: use a large value for masked entries and then take median
                # but handle even/odd N carefully.

                # Simpler: float conversion ONLY for these pixels
                s_gt1_f = s_gt1.astype(np.float32)
                s_gt1_f[~masks_gt1] = np.nan
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    med = np.nanmedian(s_gt1_f, axis=0)
                canvas_strip.reshape(-1, 3)[m_gt1.flatten()] = np.clip(
                    med, 0, 255
                ).astype(np.uint8)

            valid_mask[y0:y1][count > 0] = 255

        if not _skip_anim and N >= 4:
            anim_mask, phase_groups = self._cluster_animation_phases(frames, affines, H, W)
            if anim_mask is not None and phase_groups is not None:
                print(f"[Stitch]   Animation detected: {len(phase_groups)} phases — re-rendering anim pixels...")
                majority_group = max(phase_groups, key=len)
                sub_frames = [frames[idx] for idx in majority_group]
                sub_affines = [affines[idx] for idx in majority_group]
                sub_masks = [bg_masks[idx] for idx in majority_group]
                sub_bl = [_baselines[idx] for idx in majority_group] if _baselines is not None else None
                anim_canvas, _, _, _ = self._render_median(
                    sub_frames, sub_affines, sub_masks, H, W,
                    _baselines=sub_bl, _skip_anim=True,
                )
                anim_px = anim_mask > 0
                canvas[anim_px] = anim_canvas[anim_px]

        return canvas, valid_mask, [], []

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
        """
        Detect cyclic animation pixels via per-pixel FFT along the temporal axis,
        then cluster frames by animation phase.

        Returns
        -------
        anim_mask_full : (H, W) uint8 — 255 = animation pixel — or None.
        phase_groups   : list of frame-index lists, one per phase, or None.
        """
        N = len(frames)
        if N < 4:
            return None, None

        scale = target_w / max(W, 1)
        th = max(1, int(H * scale))
        tw = target_w

        small_stack = []
        for i in range(N):
            tx = float(affines[i][0, 2])
            ty = float(affines[i][1, 2])
            M_small = np.array([[scale, 0.0, tx * scale], [0.0, scale, ty * scale]], np.float32)
            warped = cv2.warpAffine(frames[i], M_small, (tw, th), flags=cv2.INTER_AREA)
            gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            small_stack.append(gray)

        stack_arr = np.stack(small_stack, axis=0)  # (N, th, tw)

        # Per-pixel FFT along temporal axis
        F = np.fft.rfft(stack_arr, axis=0)  # (N//2+1, th, tw)
        power = np.abs(F) ** 2
        dc_power = power[0]
        ac_power = power[1:].sum(axis=0)
        ratio = ac_power / (dc_power + ac_power + 1e-8)

        anim_mask_small = (ratio > ac_threshold).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        anim_mask_small = cv2.morphologyEx(anim_mask_small, cv2.MORPH_OPEN, kernel)
        anim_mask_small = cv2.morphologyEx(anim_mask_small, cv2.MORPH_CLOSE, kernel)

        if int(anim_mask_small.sum()) // 255 < min_anim_pixels:
            return None, None

        anim_mask_full = cv2.resize(anim_mask_small, (W, H), interpolation=cv2.INTER_NEAREST)

        # Edge-signature KMeans clustering for phase assignment
        anim_ys, anim_xs = np.where(anim_mask_small > 0)
        sigs = []
        for gray in small_stack:
            edges = cv2.Canny((gray * 255).astype(np.uint8), 50, 150)
            sigs.append(edges[anim_ys, anim_xs].astype(np.float32))

        sig_matrix = np.stack(sigs, axis=0)  # (N, P)
        n_clusters = max(2, min(8, N // 2))

        try:
            from sklearn.cluster import KMeans
            km = KMeans(n_clusters=n_clusters, n_init=5, random_state=0)
            labels = km.fit_predict(sig_matrix)
        except ImportError:
            labels = np.arange(N) % n_clusters

        phase_groups = [
            [idx for idx in range(N) if labels[idx] == k]
            for k in range(n_clusters)
            if any(labels == k)
        ]

        return anim_mask_full, phase_groups

    def _render_first(self, frames, affines, H, W):
        # Implementation of simple first-frame renderer
        canvas = np.zeros((H, W, 3), np.uint8)
        mask = np.zeros((H, W), np.uint8)
        for img, M in reversed(list(zip(frames, affines))):
            w = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR)
            m = (w.max(axis=2) > 0).astype(np.uint8) * 255
            canvas[m > 0] = w[m > 0]
            mask |= m
        return canvas, mask

    def _render_laplacian(
        self,
        frames: List[np.ndarray],
        affines: List[np.ndarray],
        bg_masks: List[Optional[np.ndarray]],
        H: int,
        W: int,
    ) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
        """
        Perfect Seamless Blender: Sequential Laplacian with Optimal Seams.
        """
        N = len(frames)
        warped_list = []
        mask_list = []
        for i, (img, M, bg) in enumerate(zip(frames, affines, bg_masks)):
            M_r = M
            w = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR)
            warped_list.append(w)
            mask = (w.max(axis=2) > 0).astype(np.uint8) * 255
            mask_list.append(mask)

        # ── Color Matching (Linear Gain Anchor to Frame 0) ─────────────────
        ref_idx = 0
        ref_img = warped_list[ref_idx].astype(np.float32)
        ref_m = mask_list[ref_idx] > 0
        colour_matched = [ref_img]
        for i in range(1, N):
            src = warped_list[i].astype(np.float32)
            vm = mask_list[i] > 0
            overlap = vm & ref_m
            if overlap.sum() > 5000:
                out = src.copy()
                for c in range(3):
                    gain = ref_img[overlap, c].mean() / (src[overlap, c].mean() + 1e-6)
                    out[..., c] = np.clip(src[..., c] * gain, 0, 255)
                colour_matched.append(out)
            else:
                colour_matched.append(src)

        # ── Sequential Seamless Blend ──────────────────────────────────────
        canvas = colour_matched[0].copy()
        canvas_m = mask_list[0].copy()

        for i in range(1, N):
            img = colour_matched[i]
            m_i = mask_list[i]
            overlap = (canvas_m > 0) & (m_i > 0)
            if not overlap.any():
                # No overlap, just paste
                canvas[m_i > 0] = img[m_i > 0]
                canvas_m[m_i > 0] = 255
                continue

            # Find optimal seam between canvas and incoming frame using DP
            ys, xs = np.where(overlap)
            y0_ov, y1_ov = int(ys.min()), int(ys.max()) + 1
            x0_ov, x1_ov = int(xs.min()), int(xs.max()) + 1
            ow = x1_ov - x0_ov
            oh = y1_ov - y0_ov

            canvas_crop = canvas[y0_ov:y1_ov, x0_ov:x1_ov].astype(np.uint8)
            img_crop = np.clip(img[y0_ov:y1_ov, x0_ov:x1_ov], 0, 255).astype(np.uint8)

            # horizontal=True → path[row] = col (vertical seam for wide overlaps)
            # horizontal=False → path[col] = row (horizontal seam for tall overlaps)
            seam_horiz = ow >= oh
            path = _seam_dp(canvas_crop, img_crop, horizontal=not seam_horiz)

            weight = np.zeros((H, W), dtype=np.float32)
            weight[m_i > 0] = 1.0
            weight[canvas_m > 0] = 0.0

            # Carve binary seam boundary into weight
            if seam_horiz:
                # horizontal=False → energy transposed → path length=ow, path[c]=row
                # pixels with row >= path[c] belong to new frame
                row_idx = np.arange(oh)
                seam_weight = (row_idx[:, np.newaxis] >= path[np.newaxis, :]).astype(np.float32)
            else:
                # horizontal=True → path length=oh, path[r]=col
                # pixels with col >= path[r] belong to new frame
                col_idx = np.arange(ow)
                seam_weight = (col_idx[np.newaxis, :] >= path[:, np.newaxis]).astype(np.float32)

            # Invert seam if the new frame extends on the opposite side of the overlap
            new_only = (m_i > 0) & (canvas_m == 0)
            if seam_horiz:
                if new_only[y1_ov:, :].sum() < new_only[:y0_ov, :].sum():
                    seam_weight = 1.0 - seam_weight
            else:
                if new_only[:, x1_ov:].sum() < new_only[:, :x0_ov].sum():
                    seam_weight = 1.0 - seam_weight

            weight[y0_ov:y1_ov, x0_ov:x1_ov] = seam_weight
            weight[~overlap] = (m_i[~overlap] > 0).astype(np.float32)

            # Character priority: if the new frame has a character in the overlap,
            # bias the weight toward 1.0 to ensure the character is sharp.
            if bg_masks[i] is not None:
                fg_i = bg_masks[i] < 127
                M_r = affines[i]
                w_fg_i = cv2.warpAffine(
                    fg_i.astype(np.uint8) * 255,
                    affines[i],
                    (W, H),
                    flags=cv2.INTER_NEAREST,
                )
                weight[w_fg_i > 127] = 1.0

            # Laplacian Multi-band blend
            canvas = _laplacian_blend(img, canvas, weight, self.bands)
            canvas_m |= m_i

        # Final foreground pass if enabled
        # We already blended everything seamlessly, but we can do a final character-priority pass
        # for any moving parts if birefnet was used.
        # For now, the sequential blend is the smoothest possible result.

        warped_fgs = []
        for i, (M, bg) in enumerate(zip(affines, bg_masks)):
            if bg is not None:
                fg = (bg < 127).astype(np.uint8) * 255
                M_r = M
                w_fg = cv2.warpAffine(fg, M_r, (W, H), flags=cv2.INTER_NEAREST)
                warped_fgs.append(w_fg)
            else:
                warped_fgs.append(np.zeros((H, W), np.uint8))

        return (
            canvas.astype(np.uint8),
            canvas_m,
            [c.astype(np.uint8) for c in colour_matched],
            warped_fgs,
        )

    def _composite_foreground(
        self,
        warped_corr: List[np.ndarray],   # Now empty from _render
        warped_fgs: List[np.ndarray],    # Now empty from _render
        canvas: np.ndarray,
        H: int,
        W: int,
        frames: List[np.ndarray],        # Added for warp-on-the-fly
        affines: List[np.ndarray],       # Added
        bg_masks: List[Optional[np.ndarray]], # Added
    ) -> np.ndarray:
        """
        Pastes the foreground from the best available frame back onto
        the median background. Warps on-the-fly to save memory.
        """
        import cv2
        import numpy as np
        N = len(frames)
        best_i = -1
        max_area = 0
        
        # 1. Find best frame (most foreground)
        # We need to warp ONLY the mask to find the area
        for i in range(N):
            if bg_masks[i] is None: continue
            fg = (bg_masks[i] < 127).astype(np.uint8) * 255
            w_fg = cv2.warpAffine(fg, affines[i], (W, H), flags=cv2.INTER_NEAREST)
            area = (w_fg > 127).sum()
            if area > max_area:
                max_area = area
                best_i = i
        
        # 2. Apply best frame foreground
        if best_i >= 0:
            fg = (bg_masks[best_i] < 127).astype(np.uint8) * 255
            w_fg = cv2.warpAffine(fg, affines[best_i], (W, H), flags=cv2.INTER_NEAREST)
            w_corr = cv2.warpAffine(frames[best_i], affines[best_i], (W, H), flags=cv2.INTER_LINEAR)
            
            fg_mask = (w_fg > 127)
            canvas[fg_mask] = w_corr[fg_mask]
            
        return canvas

    @staticmethod
    def _crop_to_valid(canvas: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        """
        Crop to the largest inscribed rectangle of valid pixels.
        Removes black borders introduced by warpAffine.
        """
        if valid_mask.max() == 0:
            return canvas
        try:
            x0, y0, x1, y1 = _largest_valid_rect(valid_mask)
            if x1 > x0 and y1 > y0:
                return canvas[y0:y1, x0:x1]
        except Exception as e:
            print(f"[Stitch]   crop_to_valid failed ({e}); returning full canvas.")
        return canvas

    # ---------------------------------------------------------------- fallback

    @staticmethod
    def _scan_stitch_fallback(
        frames: List[np.ndarray],
        output_path: str,
    ) -> Image.Image:
        """
        Fall back to OpenCV SCANS mode when the main pipeline cannot find
        enough edges.  Mirrors _merge_images_scan_stitch.
        """
        print("[Stitch] FALLBACK: using OpenCV SCANS mode.")
        cv2.ocl.setUseOpenCL(False)
        try:
            stitcher = cv2.Stitcher_create(mode=1)
        except AttributeError:
            stitcher = cv2.createStitcher(True)
        stitcher.setRegistrationResol(0.8)
        status, pano = stitcher.stitch(frames)
        if status != cv2.Stitcher_OK:
            raise RuntimeError(f"SCANS fallback failed (status={status}).")
        rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
        out = Image.fromarray(rgb)
        out.save(output_path)
        return out

    @staticmethod
    def find_optimal_sequence(
        ref_path: str,
        candidates: List[str],
        min_inliers: int = 30,
        max_overlap: float = 0.85,
    ) -> List[str]:
        """
        Finds the longest coherent sequence while dropping redundant frames.
        Prioritizes frames that extend the panorama furthest while maintaining
        robust overlap.
        """
        import cv2
        import numpy as np

        # 1. Feature Extraction (SIFT)
        sift = cv2.SIFT_create(nfeatures=1200)

        def get_feats(p):
            img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return None, None, None
            h, w = img.shape
            if w > 1024:
                img = cv2.resize(img, (1024, int(h * 1024 / w)))
            kp, des = sift.detectAndCompute(img, None)
            return kp, des, img.shape

        feats = {}
        for p in [ref_path] + list(candidates):
            if p not in feats:
                kp, des, shape = get_feats(p)
                if kp is not None:
                    feats[p] = (kp, des, shape[0], shape[1])

        if ref_path not in feats:
            return []

        sequence = [ref_path]
        used = {ref_path}
        bf = cv2.BFMatcher()

        def find_optimal_extension(query_path, pool, direction="forward"):
            q_kp, q_des, q_h, q_w = feats[query_path]
            best_p = None
            max_dist = -1.0

            # We want to find the frame that is FURTHEST away but still has enough inliers
            # This naturally drops redundant, high-overlap frames.
            for p in pool:
                if p in used or p not in feats:
                    continue
                t_kp, t_des, t_h, t_w = feats[p]

                matches = bf.knnMatch(q_des, t_des, k=2)
                good = [m for m, n in matches if m.distance < 0.75 * n.distance]
                if len(good) < min_inliers:
                    continue

                src_pts = np.float32([q_kp[m.queryIdx].pt for m in good]).reshape(
                    -1, 1, 2
                )
                dst_pts = np.float32([t_kp[m.trainIdx].pt for m in good]).reshape(
                    -1, 1, 2
                )
                M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                if M is None or mask is None:
                    continue

                inliers = int(mask.sum())
                if inliers < min_inliers:
                    continue

                # Calculate translation distance
                # M[0,2] is x-translation, M[1,2] is y-translation
                dist = np.sqrt(M[0, 2] ** 2 + M[1, 2] ** 2)
                # Enforce minimum 4% translation to drop redundant frames
                if dist < 0.15 * max(q_h, q_w):
                    continue

                # Check overlap ratio (approximate)
                # If dist is 0, overlap is 100%. If dist is width, overlap is 0%.
                # We skip if overlap is too high (> max_overlap),
                # UNLESS it's the only match we have.
                # Actually, simply picking the MAX distance handles this.

                if dist > max_dist:
                    max_dist = dist
                    best_p = p

            return best_p

        # Expand Forward
        while True:
            nxt = find_optimal_extension(sequence[-1], candidates, "forward")
            if nxt:
                sequence.append(nxt)
                used.add(nxt)
            else:
                break

        # Expand Backward
        while True:
            prev = find_optimal_extension(sequence[0], candidates, "backward")
            if prev:
                sequence.insert(0, prev)
                used.add(prev)
            else:
                break

        return sequence
