"""Reference-based colorization via entropic-regularized Optimal Transport
(roadmap §2.4, issue #188).

The dominant industrial manga colorization workflow isn't scribble-based --
an artist provides a single colored reference sheet (e.g. a character
design or a volume cover) and an entire chapter of monochrome line art is
colorized to match it (research report §5.4). This module implements that
workflow:

1. Over-segment both the reference image and the target line art into
   superpixels (SLIC).
2. Describe each superpixel by a *structural* feature vector (Gabor texture
   signature + normalized centroid position) -- matching is done on
   structure, not raw color, since the target has no color yet.
3. Solve for a soft correspondence (transport plan) between reference and
   target superpixels via the Sinkhorn algorithm, minimizing total
   structural-feature transport cost under entropic regularization
   (research report §5.4's ``min_P <P,C> + eps*H(P)`` formulation).
4. Each target superpixel's color is the transport-plan-weighted average of
   every reference superpixel's mean color.

Implemented with a from-scratch NumPy Sinkhorn solver rather than pulling in
the POT (Python Optimal Transport) library -- the algorithm is ~15 lines and
this avoids a new third-party dependency for something this self-contained;
POT remains a reasonable follow-up if a more feature-complete OT toolkit
(unbalanced OT, GPU dispatch, etc.) is ever needed. Superpixel matching uses
Gabor texture + position rather than the CLIP-embedding-based matching
described in the research report's retrieval-augmented pipelines (ColorFlow
etc.) -- those need a pretrained vision-language model; this stays
dependency-light and assumes the reference and target share a roughly
similar pose/composition (the common case for a single-character reference
sheet applied to consecutive panels of that same character), which is a
real, documented limitation, not a hidden one.
"""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np
from skimage.segmentation import slic

from .gabor import gabor_feature_bank

__all__ = ["sinkhorn", "colorize_reference"]


def sinkhorn(
    cost: np.ndarray,
    mu: np.ndarray,
    nu: np.ndarray,
    epsilon: float = 0.1,
    n_iter: int = 200,
    tol: float = 1e-9,
) -> np.ndarray:
    """Entropic-regularized Optimal Transport via Sinkhorn-Knopp iteration.

    Solves ``min_P <P, cost> + epsilon * H(P)`` subject to ``P`` having row
    marginals ``mu`` and column marginals ``nu`` (research report §5.4).

    Args:
        cost: (n, m) cost matrix, ``cost[i, j]`` = cost of transporting mass
            from source i to target j.
        mu: (n,) source marginal (must sum to the same total mass as ``nu``,
            typically both normalized to sum to 1).
        nu: (m,) target marginal.
        epsilon: entropic regularization strength -- smaller values track
            the true (unregularized) OT plan more closely but condition the
            kernel matrix more poorly; larger values are more numerically
            stable but blur the transport plan toward a uniform coupling.
        n_iter: maximum scaling iterations.
        tol: stop early once the row-marginal residual drops below this.

    Returns:
        (n, m) transport plan ``P``.
    """
    cost = cost / (cost.max() + 1e-12)  # scale-invariant: keeps exp() well-conditioned
    kernel = np.exp(-cost / epsilon)

    n, m = cost.shape
    u = np.ones(n) / n
    v = np.ones(m) / m

    for _ in range(n_iter):
        kv = kernel @ v
        kv = np.where(kv < 1e-300, 1e-300, kv)
        u_new = mu / kv

        ktu = kernel.T @ u_new
        ktu = np.where(ktu < 1e-300, 1e-300, ktu)
        v_new = nu / ktu

        # NOTE: comparing u_new*kv to mu here would be tautological (u_new is
        # defined as mu/kv, so it always matches mu to float precision) and
        # would break out after the very first iteration regardless of actual
        # convergence. Track iterate stability instead -- how much v moved --
        # which only shrinks to ~0 once both marginals are actually satisfied.
        residual = np.abs(v_new - v).sum()
        u, v = u_new, v_new
        if residual < tol:
            break

    return u[:, None] * kernel * v[None, :]


def _superpixel_features_and_colors(
    gray: np.ndarray,
    rgb: np.ndarray,
    n_segments: int,
    compactness: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Segment `rgb`/`gray` into superpixels and summarize each one.

    Returns:
        (labels, features, mean_colors, weights) where ``labels`` is the
        HxW SLIC label map, ``features`` is (K, D) structural feature
        vectors (Gabor texture + normalized centroid), ``mean_colors`` is
        (K, 3) mean RGB per superpixel, and ``weights`` is (K,) each
        superpixel's pixel-count share of the image (used as the OT
        marginal -- larger superpixels carry proportionally more mass).
    """
    h, w = gray.shape
    labels = slic(rgb, n_segments=n_segments, compactness=compactness, start_label=0, channel_axis=-1)
    n_labels = labels.max() + 1

    texture = gabor_feature_bank(gray)  # HxWxC
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")

    flat_labels = labels.ravel()
    flat_texture = texture.reshape(-1, texture.shape[-1])
    flat_rgb = rgb.reshape(-1, 3).astype(np.float64)
    flat_y = yy.ravel().astype(np.float64) / max(h - 1, 1)
    flat_x = xx.ravel().astype(np.float64) / max(w - 1, 1)

    # Vectorized per-superpixel aggregation (np.bincount groupby-by-label)
    # instead of an O(n_labels * n_pixels) Python loop over boolean masks --
    # the loop was the dominant cost for a realistic superpixel count.
    counts = np.bincount(flat_labels, minlength=n_labels).astype(np.float64)
    counts_safe = np.where(counts < 1, 1, counts)

    texture_sums = np.zeros((n_labels, flat_texture.shape[1]), dtype=np.float64)
    for c in range(flat_texture.shape[1]):
        texture_sums[:, c] = np.bincount(flat_labels, weights=flat_texture[:, c], minlength=n_labels)
    texture_mean = texture_sums / counts_safe[:, None]

    y_mean = np.bincount(flat_labels, weights=flat_y, minlength=n_labels) / counts_safe
    x_mean = np.bincount(flat_labels, weights=flat_x, minlength=n_labels) / counts_safe

    color_sums = np.zeros((n_labels, 3), dtype=np.float64)
    for c in range(3):
        color_sums[:, c] = np.bincount(flat_labels, weights=flat_rgb[:, c], minlength=n_labels)
    mean_colors = color_sums / counts_safe[:, None]

    features = np.concatenate([texture_mean, y_mean[:, None], x_mean[:, None]], axis=1)
    weights = counts / counts.sum()
    return labels, features, mean_colors, weights


def colorize_reference(
    target_gray: np.ndarray,
    reference_rgb: np.ndarray,
    n_segments_target: int = 200,
    n_segments_reference: int = 200,
    compactness: float = 10.0,
    epsilon: float = 0.05,
    max_solve_dim: int = 400,
) -> np.ndarray:
    """Colorize `target_gray` line art to match `reference_rgb`'s palette,
    via superpixel-level Optimal Transport (see module docstring).

    Args:
        target_gray: HxW uint8 grayscale line-art image to colorize.
        reference_rgb: H'xW'x3 uint8 RGB reference image (different
            resolution from the target is fine -- superpixels are matched
            by normalized structural features, not pixel-aligned).
        n_segments_target: approximate SLIC superpixel count for the target.
        n_segments_reference: approximate SLIC superpixel count for the reference.
        compactness: SLIC compactness (higher = more square/regular superpixels).
        epsilon: Sinkhorn entropic regularization strength (see :func:`sinkhorn`).
        max_solve_dim: caps the longest side used for SLIC/Gabor/Sinkhorn
            (both target and reference are downscaled independently before
            segmentation); the transported chrominance is then upsampled
            back onto full-resolution target luminance. Superpixel colors
            are already a coarse, per-region signal, so downscaling loses
            little; this is what keeps solve time roughly bounded regardless
            of source resolution (SLIC + dense per-pixel Gabor features +
            an O(n_ref * n_target) Sinkhorn cost matrix all scale with pixel
            count). Pass 0 to disable and always solve at full resolution.

    Returns:
        HxWx3 uint8 RGB colorized image. As with the scribble colorizers,
        the target's own luminance is preserved exactly (only chrominance
        comes from the transport-plan-weighted reference colors).
    """
    if target_gray.ndim != 2:
        raise ValueError(f"target_gray must be a 2-D HxW array, got shape {target_gray.shape}")
    if reference_rgb.ndim != 3 or reference_rgb.shape[2] != 3:
        raise ValueError(f"reference_rgb must be an HxWx3 array, got shape {reference_rgb.shape}")

    from backend.src.core.telemetry import MANGA_COLORIZE_LOCK

    with MANGA_COLORIZE_LOCK:
        return _colorize_reference_impl(
            target_gray, reference_rgb, n_segments_target, n_segments_reference, compactness, epsilon, max_solve_dim
        )


def _colorize_reference_impl(
    target_gray: np.ndarray,
    reference_rgb: np.ndarray,
    n_segments_target: int,
    n_segments_reference: int,
    compactness: float,
    epsilon: float,
    max_solve_dim: int,
) -> np.ndarray:
    h, w = target_gray.shape
    target_u8 = target_gray.astype(np.uint8) if target_gray.dtype != np.uint8 else target_gray

    # Downscale independently for the solve -- SLIC, dense per-pixel Gabor
    # features, and the O(n_ref * n_target) Sinkhorn cost matrix all scale
    # with pixel count, so this is what keeps solve time roughly bounded
    # regardless of source resolution (mirrors max_solve_dim in
    # colorization.py / screentone.py).
    solve_gray = target_u8
    if max_solve_dim and max(h, w) > max_solve_dim:
        scale = max_solve_dim / max(h, w)
        solve_gray = cv2.resize(target_u8, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)

    ref_u8 = reference_rgb.astype(np.uint8)
    rh, rw = ref_u8.shape[:2]
    if max_solve_dim and max(rh, rw) > max_solve_dim:
        rscale = max_solve_dim / max(rh, rw)
        ref_u8 = cv2.resize(ref_u8, (max(1, round(rw * rscale)), max(1, round(rh * rscale))), interpolation=cv2.INTER_AREA)

    solve_rgb = cv2.cvtColor(solve_gray, cv2.COLOR_GRAY2RGB)
    reference_gray = cv2.cvtColor(ref_u8, cv2.COLOR_RGB2GRAY)

    target_labels, target_feat, _target_colors, target_w = _superpixel_features_and_colors(
        solve_gray, solve_rgb, n_segments_target, compactness
    )
    _ref_labels, ref_feat, ref_colors, ref_w = _superpixel_features_and_colors(
        reference_gray, ref_u8, n_segments_reference, compactness
    )

    # Standardize the combined feature space so texture and position
    # contribute comparably to the cost (position is naturally in [0, 1]
    # already; texture channels were per-image standardized by
    # gabor_feature_bank, but the two images' distributions can still
    # differ slightly).
    combined = np.concatenate([ref_feat, target_feat], axis=0)
    mean = combined.mean(axis=0, keepdims=True)
    std = combined.std(axis=0, keepdims=True)
    std = np.where(std < 1e-8, 1.0, std)
    ref_feat_n = (ref_feat - mean) / std
    target_feat_n = (target_feat - mean) / std

    # Squared-Euclidean cost between every (reference, target) superpixel pair.
    diff = ref_feat_n[:, None, :] - target_feat_n[None, :, :]
    cost = np.sum(diff ** 2, axis=-1)

    plan = sinkhorn(cost, ref_w, target_w, epsilon=epsilon)

    # Each target superpixel's color = weighted average of reference colors,
    # weighted by that target's column of the transport plan.
    col_sum = plan.sum(axis=0, keepdims=True)
    col_sum = np.where(col_sum < 1e-12, 1.0, col_sum)
    normalized_plan = plan / col_sum  # (n_ref, n_target), columns sum to 1
    target_colors = normalized_plan.T @ ref_colors  # (n_target, 3)

    sh, sw = target_labels.shape
    out_rgb = np.zeros((sh, sw, 3), dtype=np.float64)
    for label in range(target_colors.shape[0]):
        out_rgb[target_labels == label] = target_colors[label]

    if (sh, sw) != (h, w):
        out_rgb = cv2.resize(out_rgb.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)

    # Preserve the target's own luminance exactly (same contract as the
    # scribble colorizers): only chrominance comes from the transport plan.
    out_bgr = cv2.cvtColor(out_rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
    out_ycrcb = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)

    target_bgr = cv2.cvtColor(target_u8, cv2.COLOR_GRAY2BGR)
    target_ycrcb = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2YCrCb)
    out_ycrcb[:, :, 0] = target_ycrcb[:, :, 0]

    out_ycrcb = np.clip(out_ycrcb, 0, 255).astype(np.uint8)
    final_bgr = cv2.cvtColor(out_ycrcb, cv2.COLOR_YCrCb2BGR)
    return cv2.cvtColor(final_bgr, cv2.COLOR_BGR2RGB)
