"""Graph-cut (Boykov-Kolmogorov) temporal coherence refinement (roadmap
§3.2, issue #193).

§3.1's 3D quadratic-cost propagation (``temporal.py``, issue #192) solves a
single combined sparse linear system across a whole sequence, which works
well when local intensity tracking between adjacent frames is reliable, but
degrades under fast motion/occlusion: a big intensity jump between frame
``t`` and its temporal neighbors distorts the intensity-correlation weights
the Levin solver leans on, which can leak an implausible chrominance value
into a frame even though the *rest* of the sequence solved cleanly. This
module adds a second pass that treats the whole sequence's already-solved
per-frame chrominance (typically ``temporal.py``'s
``colorize_scribble_sequence()`` output) as a *label hypothesis* and uses a
Boykov-Kolmogorov min-cut/max-flow solve (via `PyMaxflow
<https://github.com/pmneila/PyMaxflow>`_, which wraps Boykov & Kolmogorov's
reference C++ implementation -- not reimplemented here, per the roadmap's
own recommendation) to decide, per pixel, whether to keep that value or fall
back to a neighbor-frame-blended alternative.

**Formulation and deliberate simplification.** The roadmap's MRF energy is
``E(L) = sum_p D_p(L_p) + sum_(p,q) V_p,q(L_p,L_q)``, generically over an
open-ended label set (e.g. one label per candidate color). A full
multi-label alpha-expansion solve is real scope creep for a first pass --
it needs repeated per-label binary sub-solves and a submodularity-safe
smoothness term across arbitrary color pairs. Instead, mirroring this
session's other modules (see ``colorization.py``, ``optimal_transport.py``,
``temporal.py`` docstrings for the same kind of documented, deliberate
narrowing), this module ships a **2-label binary graph-cut per frame**:

* Label ``OWN``: trust this frame's own already-solved chrominance
  (typically from ``colorize_scribble_sequence()``).
* Label ``BLEND``: distrust it, and fall back to the chrominance of its
  temporal neighbor frame(s) at the same spatial location instead (the mean
  of frame ``t-1`` and ``t+1`` for interior frames, or the single available
  neighbor at a sequence boundary).

This exactly matches the roadmap's stated pain point (suppress flicker/
inconsistency where §3.1 broke down under fast motion) without requiring an
open-ended label space -- the two competing hypotheses considered are
"trust this frame" vs. "trust its neighbors", the natural binary reduction
of the general formulation for a *coherence-refinement* pass (as opposed to
a from-scratch colorization pass, which is what §2.1/§2.4/§3.1 already do).

**Data term** ``D_p(L_p)``: for each pixel, ``flicker_p`` is the L1 distance
between the OWN and BLEND chrominance hypotheses (0 if they already agree,
so the label choice is free either way), and ``motion_p`` is the mean
absolute grayscale intensity difference to the available temporal
neighbor(s), normalized to [0, 1] -- a proxy for exactly the failure mode
this module targets: a big appearance change between frames is where local
intensity-correlation tracking (which §3.1's solver depends on) is least
trustworthy.

* ``D_p(OWN)   = data_weight * motion_p * flicker_p``
* ``D_p(BLEND) = data_weight * (1 - motion_p) * flicker_p``

High motion + high flicker pushes the cut toward ``BLEND`` (distrust the
frame's own solve where tracking plausibly broke down); low motion + high
flicker pushes it toward ``OWN`` (the disagreement isn't explained by
motion, so there's no reason to override the original solve). When
``flicker_p`` is ~0 both costs are ~0 and the smoothness term alone decides
(pulling the pixel toward whatever its neighborhood already prefers).

**Smoothness term** ``V_p,q(L_p,L_q)``: a Potts penalty (0 if
``L_p == L_q``, a positive constant otherwise) weighted by Gabor
texture-feature distance between ``p`` and ``q`` (``gabor.py``, issue #185),
using the *exact same* Gaussian-kernel affinity ``screentone.py`` already
uses for its own smoothness/halting term: ``w_pq = exp(-||T(p)-T(q)||^2 /
(2*sigma^2))``. This keeps the OWN/BLEND decision spatially coherent within
a texture region (e.g. a whole screentoned patch flips together rather than
pixel-by-pixel salt-and-pepper), which is what prevents the refinement pass
from *introducing* its own flicker. Symmetric-Potts-with-nonnegative-weight
pairwise terms are submodular, which is exactly the condition
Boykov-Kolmogorov's binary min-cut requires for an exact (not merely
approximate) solution -- unlike general multi-label alpha-expansion, no
approximation guarantees are needed here.

Unlike ``colorization.py``/``temporal.py``'s configurable ``win_rad``
window, the smoothness term here is over the standard 4-connected
(von Neumann) pixel grid -- the conventional neighborhood for image
segmentation graph-cuts (including the original Boykov-Kolmogorov papers'
own examples) and the natural fit for PyMaxflow's grid-graph helpers.
"""

from __future__ import annotations

import cv2
import maxflow
import numpy as np

from ..features.gabor import gabor_feature_bank

__all__ = ["build_temporal_coherence_graph", "graph_cut_temporal_refine"]


def _frame_chroma(rgb_frame: np.ndarray) -> np.ndarray:
    """RGB uint8 HxWx3 frame -> HxWx2 float64 (Cr, Cb)."""
    bgr = cv2.cvtColor(rgb_frame.astype(np.uint8), cv2.COLOR_RGB2BGR)
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)
    return ycrcb[:, :, 1:3]


def build_temporal_coherence_graph(
    data_cost_own: np.ndarray,
    data_cost_blend: np.ndarray,
    features: np.ndarray,
    smooth_weight: float = 1.0,
    texture_sigma: float = 1.0,
) -> "maxflow.GraphFloat":
    """Build (but do not solve) the per-frame binary min-cut graph.

    Args:
        data_cost_own: HxW cost of choosing the OWN label at each pixel.
        data_cost_blend: HxW cost of choosing the BLEND label, same shape.
        features: HxWxN texture feature array (see
            :func:`gabor.gabor_feature_bank`) used for the smoothness term.
        smooth_weight: overall scale on the pairwise Potts term.
        texture_sigma: Gaussian kernel bandwidth over feature-space
            distance -- same role as
            :func:`screentone.build_texture_affinity_system`'s ``sigma``.

    Returns:
        A ``maxflow.GraphFloat`` with grid nodes, terminal (data) edges, and
        4-connected pairwise (smoothness) edges already added -- call
        ``.maxflow()`` then ``.get_grid_segments(nodeids)`` to solve (see
        :func:`graph_cut_temporal_refine` for the full pipeline). Returned
        pre-solve so tests/callers can inspect node/edge counts, mirroring
        this package's ``build_levin_system``/``build_texture_affinity_system``
        pattern of exposing the assembled-but-unsolved system.
    """
    if data_cost_own.shape != data_cost_blend.shape:
        raise ValueError("data_cost_own and data_cost_blend must have the same shape")
    if features.shape[:2] != data_cost_own.shape:
        raise ValueError("features' spatial shape must match the data cost maps")

    h, w = data_cost_own.shape
    g = maxflow.GraphFloat()
    nodeids = g.add_grid_nodes((h, w))

    # Terminal edges encode the data term. PyMaxflow's convention (verified
    # empirically): a node lands on the SINK side (get_grid_segments==True)
    # iff its S->node edge is the cheap one to cut, at cost `sourcecaps`; it
    # lands on the SOURCE side (False) at cost `sinkcaps`. We use SINK=BLEND,
    # SOURCE=OWN, so sourcecaps=D(BLEND), sinkcaps=D(OWN).
    g.add_grid_tedges(nodeids, data_cost_blend, data_cost_own)

    two_sigma_sq = 2.0 * texture_sigma * texture_sigma

    # Horizontal (right) neighbor pairs.
    if w > 1:
        diff_h = features[:, 1:, :] - features[:, :-1, :]
        weight_h = smooth_weight * np.exp(-np.sum(diff_h * diff_h, axis=-1) / two_sigma_sq)
        i_h = nodeids[:, :-1].ravel()
        j_h = nodeids[:, 1:].ravel()
        g.add_edges(i_h, j_h, weight_h.ravel(), weight_h.ravel())

    # Vertical (down) neighbor pairs.
    if h > 1:
        diff_v = features[1:, :, :] - features[:-1, :, :]
        weight_v = smooth_weight * np.exp(-np.sum(diff_v * diff_v, axis=-1) / two_sigma_sq)
        i_v = nodeids[:-1, :].ravel()
        j_v = nodeids[1:, :].ravel()
        g.add_edges(i_v, j_v, weight_v.ravel(), weight_v.ravel())

    return g


def graph_cut_temporal_refine(
    gray_stack: np.ndarray,
    color_stack: np.ndarray,
    data_weight: float = 1.0,
    smooth_weight: float = 1.0,
    texture_sigma: float = 1.0,
    gabor_kwargs: dict | None = None,
) -> np.ndarray:
    """Refine a colorized sequence's temporal coherence with a per-frame
    Boykov-Kolmogorov graph-cut (see module docstring for the full
    formulation).

    Typical usage: pass ``colorize_scribble_sequence()``'s output (or
    ``colorize_reference()``'s per-frame output) as ``color_stack`` -- this
    function does not colorize anything itself, it decides, per pixel,
    whether that already-solved value should be kept or replaced by a
    neighbor-frame-blended alternative, to suppress flicker/inconsistency
    introduced where local intensity tracking broke down (fast motion,
    occlusion).

    Args:
        gray_stack: TxHxW uint8 (or float) grayscale line-art frames --
            same sequence used to produce ``color_stack``.
        color_stack: TxHxWx3 uint8 RGB, already-colorized sequence (the
            data-term source; see module docstring).
        data_weight: overall scale on the data term.
        smooth_weight: overall scale on the pairwise smoothness term.
        texture_sigma: Gabor feature-distance Gaussian kernel bandwidth.
        gabor_kwargs: optional kwargs forwarded to
            :func:`gabor.gabor_feature_bank` (e.g. ``orientations``,
            ``frequencies``).

    Returns:
        TxHxWx3 uint8 RGB, same shape/dtype as ``color_stack``. Luminance is
        always taken from ``gray_stack`` unchanged, matching every other
        colorizer's contract in this package.
    """
    if gray_stack.ndim != 3:
        raise ValueError(f"gray_stack must be a 3-D TxHxW array, got shape {gray_stack.shape}")
    if color_stack.shape[:3] != gray_stack.shape or color_stack.shape[3] != 3:
        raise ValueError("color_stack must have shape gray_stack.shape + (3,)")
    if gray_stack.shape[0] < 2:
        raise ValueError("graph_cut_temporal_refine needs at least 2 frames -- a single frame has no temporal neighbor to blend with")

    from backend.src.core.telemetry import MANGA_COLORIZE_LOCK

    with MANGA_COLORIZE_LOCK:
        return _graph_cut_temporal_refine_impl(
            gray_stack, color_stack, data_weight, smooth_weight, texture_sigma, gabor_kwargs or {}
        )


def _graph_cut_temporal_refine_impl(
    gray_stack: np.ndarray,
    color_stack: np.ndarray,
    data_weight: float,
    smooth_weight: float,
    texture_sigma: float,
    gabor_kwargs: dict,
) -> np.ndarray:
    t_dim, h, w = gray_stack.shape
    gray_u8 = gray_stack.astype(np.uint8) if gray_stack.dtype != np.uint8 else gray_stack

    chroma = np.stack([_frame_chroma(color_stack[t]) for t in range(t_dim)], axis=0)  # TxHxWx2
    gray_f = gray_u8.astype(np.float64)

    out_rgb = np.empty_like(color_stack)

    for t in range(t_dim):
        neighbors = []
        if t > 0:
            neighbors.append(t - 1)
        if t < t_dim - 1:
            neighbors.append(t + 1)

        blend_chroma = np.mean([chroma[n] for n in neighbors], axis=0)
        motion = np.mean([np.abs(gray_f[t] - gray_f[n]) for n in neighbors], axis=0) / 255.0

        own_chroma = chroma[t]
        flicker = np.sum(np.abs(own_chroma - blend_chroma), axis=-1) / 510.0  # in [0, 1]

        data_cost_own = data_weight * motion * flicker
        data_cost_blend = data_weight * (1.0 - motion) * flicker

        features = gabor_feature_bank(gray_u8[t], **gabor_kwargs)
        g = build_temporal_coherence_graph(
            data_cost_own, data_cost_blend, features, smooth_weight=smooth_weight, texture_sigma=texture_sigma
        )
        nodeids = np.arange(h * w, dtype=np.int64).reshape(h, w)
        g.maxflow()
        use_blend = g.get_grid_segments(nodeids)  # True => BLEND chosen

        refined_chroma = np.where(use_blend[:, :, None], blend_chroma, own_chroma)

        gray_bgr = cv2.cvtColor(gray_u8[t], cv2.COLOR_GRAY2BGR)
        out_ycrcb = cv2.cvtColor(gray_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)
        out_ycrcb[:, :, 1:3] = refined_chroma
        out_ycrcb = np.clip(out_ycrcb, 0, 255).astype(np.uint8)

        out_bgr = cv2.cvtColor(out_ycrcb, cv2.COLOR_YCrCb2BGR)
        out_rgb[t] = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)

    return out_rgb
