"""
Global Levenberg-Marquardt bundle adjustment over an affine edge graph.

Robustness: the solver uses a Cauchy (Lorentzian) loss function via scipy's
``loss='cauchy'`` mode, which is the GNC (Graduated Non-Convexity) approach
recommended in §1.1C of the ASP roadmap.  The Cauchy loss down-weights
residuals beyond ``f_scale`` pixels, making the solver inherently robust to
outlier edges that survive the post-solve residual pruning step.

f_scale=10.0 px means edges with a 10px deviation from the consensus are
weighted at 50%, 20px at 20%, 50px at ~5%.  Genuine good edges (< 5px
residual) are unaffected.  Override via ``ASP_BA_F_SCALE`` env var.
"""

from __future__ import annotations

import os
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares
from backend.src.constants import DY_RATIO_THRESH, DY_ABS_THRESH

try:
    _BA_F_SCALE = float(os.environ.get("ASP_BA_F_SCALE", "10.0"))
except ValueError:
    _BA_F_SCALE = 10.0


_ST_INLIER_THRESHOLD = 50.0  # §1.1B: max allowed disagreement (px) vs spanning-tree reference


def _spanning_tree_inlier_filter(
    edges: List[Dict],
    num_frames: int,
    inlier_threshold: float = _ST_INLIER_THRESHOLD,
) -> List[Dict]:
    """§1.1B: Consensus pre-filter via maximum-weight spanning tree.

    Builds a spanning tree from the highest-weight edges (most reliable
    matches first, Kruskal greedy order), then uses a BFS pass to derive
    a reference translation for every frame.  Any edge whose observed
    dx/dy disagrees with that reference by more than *inlier_threshold*
    pixels is removed before the Levenberg-Marquardt solve.

    Spanning-tree edges always pass (their residual is zero by construction),
    so the graph is guaranteed to remain connected after filtering.

    Falls back to returning all edges unchanged when:
    - fewer than 2 edges, or fewer than 2 frames
    - the spanning tree cannot reach every frame (disconnected graph)
    - fewer than max(2, num_frames-1) inliers survive
    """
    if len(edges) < 2 or num_frames < 2:
        return edges

    # ── Step 1: build spanning tree (greedy, highest-weight-first) ──────────
    sorted_edges = sorted(edges, key=lambda e: float(e.get("weight", 1.0)), reverse=True)

    parent: List[int] = list(range(num_frames))

    def _find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    tree_adj: Dict[int, List[Tuple[int, float, float]]] = {
        f: [] for f in range(num_frames)
    }
    n_tree_edges = 0
    for e in sorted_edges:
        i, j = int(e["i"]), int(e["j"])
        if not (0 <= i < num_frames and 0 <= j < num_frames):
            continue
        pi, pj = _find(i), _find(j)
        if pi != pj:
            parent[pi] = pj
            dtx = -float(e["M"][0, 2])
            dty = -float(e["M"][1, 2])
            tree_adj[i].append((j, dtx, dty))
            tree_adj[j].append((i, -dtx, -dty))
            n_tree_edges += 1
        if n_tree_edges == num_frames - 1:
            break

    # ── Step 2: BFS from frame 0 to compute reference translations ──────────
    tx_ref: List[Optional[float]] = [None] * num_frames
    ty_ref: List[Optional[float]] = [None] * num_frames
    tx_ref[0] = 0.0
    ty_ref[0] = 0.0
    queue: deque = deque([0])
    while queue:
        curr = queue.popleft()
        for nbr, dtx, dty in tree_adj[curr]:
            if tx_ref[nbr] is None:
                tx_ref[nbr] = tx_ref[curr] + dtx  # type: ignore[operator]
                ty_ref[nbr] = ty_ref[curr] + dty  # type: ignore[operator]
                queue.append(nbr)

    # disconnected graph — spanning tree can't cover all frames
    if any(t is None for t in ty_ref):
        return edges

    # ── Step 3: evaluate every edge against the reference ───────────────────
    inlier_edges: List[Dict] = []
    for e in edges:
        i, j = int(e["i"]), int(e["j"])
        pred_dx = tx_ref[j] - tx_ref[i]  # type: ignore[operator]
        pred_dy = ty_ref[j] - ty_ref[i]  # type: ignore[operator]
        obs_dx = -float(e["M"][0, 2])
        obs_dy = -float(e["M"][1, 2])
        residual = float(
            np.sqrt((pred_dx - obs_dx) ** 2 + (pred_dy - obs_dy) ** 2)
        )
        if residual <= inlier_threshold:
            inlier_edges.append(e)

    # safety: keep original if too few inliers remain (graph connectivity)
    if len(inlier_edges) < max(2, num_frames - 1):
        return edges

    return inlier_edges


def _bundle_adjust_affine(
    edges: List[Dict],
    num_frames: int,
    iterations: int = 200,
    use_affine: bool = True,  # If True, 6-DOF. If False, 2-DOF translation only.
) -> List[np.ndarray]:
    """
    Global Levenberg-Marquardt bundle adjustment for Affine (6-DOF) or Translation (2-DOF).

    We use a strict translation-only BA (rotation/scale locked to identity)
    to eliminate 'fan' or 'spiraling' distortion.

    The function minimises:
        Sum || (p_i + t_i) - (p_j + t_j) ||^2  for anchor points p

    Frame 0 is pinned at identity (zero translation).

    Parameters
    ----------
    edges : list of dicts with keys:
        'i', 'j'   — frame indices (i < j)
        'M'        — (2,3) float32 affine matrix mapping i -> j (only translation is used)
        'pts_i'    — (K,2) float32 sample points in frame i coords
        'pts_j'    — (K,2) float32 matched points in frame j coords
        'weight'   — float, confidence weight
    num_frames : total number of frames (including frame 0).

    Returns
    -------
    List of (2, 3) float32 translation-only matrices, one per frame.
    Frame 0 is identity.
    """
    # §1.1B: spanning-tree pre-filter — remove edges inconsistent with the
    # highest-weight spanning tree before running the LM solve.  Tree edges
    # (residual=0 by construction) are always kept, so the graph stays connected.
    edges = _spanning_tree_inlier_filter(edges, num_frames)

    # DOF for Partial Affine: [a, b, tx, ty]
    # Matrix: [[a, b, tx], [-b, a, ty]]
    # This preserves aspect ratio and is much more stable for 2D digital pans.
    dof = 4 if use_affine else 2
    x0 = np.zeros(num_frames * dof, np.float64)

    # Initialise identity for all frames
    if use_affine:
        for f in range(num_frames):
            x0[f * 4] = 1.0  # a (scale*cos(theta))

    # Initial sequential guess.
    # M convention: dy = y_j - y_i (forward-shift: LoFTR/PC).
    # Canvas placement: ty_j = ty_i - dy, so we accumulate with -M_raw.
    for f in range(1, num_frames):
        for e in edges:
            if e["i"] == f - 1 and e["j"] == f:
                M_raw = e["M"]
                if use_affine:
                    x0[f * 4] = 1.0
                    x0[f * 4 + 2] = x0[(f - 1) * 4 + 2] - float(M_raw[0, 2])
                    x0[f * 4 + 3] = x0[(f - 1) * 4 + 3] - float(M_raw[1, 2])
                else:
                    x0[f * 2] = x0[(f - 1) * 2] - float(M_raw[0, 2])
                    x0[f * 2 + 1] = x0[(f - 1) * 2 + 1] - float(M_raw[1, 2])
                break

    def residuals(x: np.ndarray) -> np.ndarray:
        res = []
        for e in edges:
            i, j, w = e["i"], e["j"], float(e.get("weight", 1.0))
            if use_affine:
                # Frame i
                ai, bi, txi, tyi = x[i * 4 : i * 4 + 4]
                Mi = np.array([[ai, bi, txi], [-bi, ai, tyi]])
                # Frame j
                aj, bj, txj, tyj = x[j * 4 : j * 4 + 4]
                Mj = np.array([[aj, bj, txj], [-bj, aj, tyj]])
            else:
                Mi = np.array(
                    [[1, 0, x[i * 2]], [0, 1, x[i * 2 + 1]]], dtype=np.float64
                )
                Mj = np.array(
                    [[1, 0, x[j * 2]], [0, 1, x[j * 2 + 1]]], dtype=np.float64
                )

            pts_i = e["pts_i"].astype(np.float64)
            pts_j = e["pts_j"].astype(np.float64)

            pi_global = (Mi[:, :2] @ pts_i.T + Mi[:, 2:3]).T
            pj_global = (Mj[:, :2] @ pts_j.T + Mj[:, 2:3]).T

            diff = pi_global - pj_global
            res.extend((diff * w).flatten())

        # Anchor frame 0 firmly at identity
        reg_anchor = 2000.0
        if use_affine:
            res.extend((x[0:4] - [1.0, 0.0, 0.0, 0.0]) * reg_anchor)
        else:
            res.extend(x[0:2] * reg_anchor)

        # Global Identity Prior (Self-Regularization)
        # Prevents scale collapse and keeps rotation near zero
        reg_identity = 1e5
        if use_affine:
            for f in range(1, num_frames):
                res.append((x[f * 4] - 1.0) * reg_identity)  # a
                res.append(x[f * 4 + 1] * reg_identity)  # b

        # P1.6 — StabStitch trajectory smoothness regulariser.
        # Minimises second-order temporal acceleration of translation trajectories,
        # preventing warping-shake (micro-jitter) in the temporal median output.
        # λ=0.10 allows ~1px/frame² acceleration — enough for genuine variable-speed
        # pans while suppressing noise-driven jitter.
        reg_traj = 0.10
        tx_slot = 2 if use_affine else 0
        ty_slot = 3 if use_affine else 1
        stride = 4 if use_affine else 2
        for f in range(1, num_frames - 1):
            tx_acc = (
                x[(f + 1) * stride + tx_slot]
                - 2 * x[f * stride + tx_slot]
                + x[(f - 1) * stride + tx_slot]
            )
            ty_acc = (
                x[(f + 1) * stride + ty_slot]
                - 2 * x[f * stride + ty_slot]
                + x[(f - 1) * stride + ty_slot]
            )
            res.append(tx_acc * reg_traj)
            res.append(ty_acc * reg_traj)

        return np.array(res, np.float64)

    # GNC robust loss (§1.1C): Cauchy loss down-weights outlier edges whose
    # residuals exceed f_scale px.  This makes the solver inherently resistant
    # to bad LoFTR matches that corrupt the global bundle even when the post-
    # solve residual pruning below cannot catch them (e.g., when the bad edge's
    # residual is within 3× of the median because the median itself is inflated
    # by multiple bad edges).  f_scale=10px means good matches (< 5px) are
    # unaffected; outliers (50–200px) contribute ~5% of their L2 weight.
    result = least_squares(
        residuals,
        x0,
        method="trf",
        loss="cauchy",
        f_scale=_BA_F_SCALE,
        ftol=1e-6,
        xtol=1e-6,
        gtol=1e-6,
        max_nfev=iterations * num_frames,
    )
    x_opt = result.x

    def _extract_affines(x: np.ndarray) -> List[np.ndarray]:
        """Build affine matrices from the flat parameter vector."""
        mats: List[np.ndarray] = []
        for f in range(num_frames):
            if use_affine:
                a, b, tx, ty = x[f * 4 : f * 4 + 4]
                M = np.array([[a, b, tx], [-b, a, ty]], dtype=np.float32)
            else:
                M = np.eye(2, 3, dtype=np.float32)
                M[0, 2] = float(x[f * 2])
                M[1, 2] = float(x[f * 2 + 1])
            mats.append(M)
        return mats

    out = _extract_affines(x_opt)

    # §1.1D: Adaptive GNC f_scale re-solve (S30).
    # If the median post-solve edge residual is significantly larger than
    # _BA_F_SCALE, the Cauchy loss has been over-penalising legitimate edges.
    # Re-solve once with an f_scale derived from the data so the loss treats
    # the actual noise floor as the inlier boundary, not a hardcoded constant.
    _adapt_scale = _compute_adaptive_f_scale(edges, out, floor=_BA_F_SCALE)
    if _adapt_scale > _BA_F_SCALE * 1.5:
        result = least_squares(
            residuals,
            x_opt,
            method="trf",
            loss="cauchy",
            f_scale=_adapt_scale,
            ftol=1e-6,
            xtol=1e-6,
            gtol=1e-6,
            max_nfev=iterations * num_frames,
        )
        x_opt = result.x
        out = _extract_affines(x_opt)

    # ── Outlier rejection ───────────────────────────────────────────────────
    # Two-pronged approach:
    #   1. Point-wise residuals: edges whose BA-predicted displacement disagrees
    #      with their observed displacement indicate noisy/wrong LoFTR matches.
    #   2. Edge-displacement outliers: even when the solver perfectly satisfies
    #      all edges (zero residual), an edge whose observed displacement is a
    #      statistical outlier relative to the other edges should be pruned.
    # This handles both noisy real data (prong 1) and the synthetic/clean case
    # where one edge has an anomalous dy but consistent internal points (prong 2).
    if len(edges) >= 3:
        # Prong 1: point-wise residual check
        edge_residuals: List[float] = []
        for e in edges:
            ei, ej = e["i"], e["j"]
            pred_dx = float(out[ej][0, 2]) - float(out[ei][0, 2])
            pred_dy = float(out[ej][1, 2]) - float(out[ei][1, 2])
            obs_dx = -float(e["M"][0, 2])
            obs_dy = -float(e["M"][1, 2])
            res_val = np.sqrt((pred_dx - obs_dx) ** 2 + (pred_dy - obs_dy) ** 2)
            edge_residuals.append(res_val)

        med_res = float(np.median(edge_residuals))
        res_threshold = max(3.0 * med_res, 30.0)

        # Prong 2: edge-displacement outlier check
        # Compare each edge's observed displacement magnitude to the median.
        edge_dy_vals = [abs(float(e["M"][1, 2])) for e in edges]
        med_dy = float(np.median(edge_dy_vals))

        # An edge is an outlier if its |dy| is > 2.5× the median AND the
        # absolute deviation exceeds 100px (to avoid false positives on
        # datasets with naturally varying overlap).
        clean_mask: List[bool] = []
        for idx, e in enumerate(edges):
            # Check prong 1: point-wise residual
            if edge_residuals[idx] > res_threshold:
                clean_mask.append(False)
                continue
            # Check prong 2: edge displacement outlier
            dy_val = abs(float(e["M"][1, 2]))
            if (
                dy_val > (med_dy * DY_RATIO_THRESH)
                and abs(dy_val - med_dy) > DY_ABS_THRESH
            ):
                clean_mask.append(False)
                continue
            clean_mask.append(True)

        n_pruned = sum(not k for k in clean_mask)
        if n_pruned > 0:
            clean_edges = [e for e, keep in zip(edges, clean_mask) if keep]
            # Re-solve as long as we have some edges. If the graph is disconnected,
            # unconstrained frames will remain at ty=0, which will trigger the
            # min_gap validation failure later and properly fall back to SCANS.
            if len(clean_edges) >= 2:
                pruned_info = ", ".join(
                    f"{e['i']}→{e['j']}"
                    for e, keep in zip(edges, clean_mask)
                    if not keep
                )
                print(
                    f"[Stitch]   BA outlier rejection: pruned {n_pruned}/{len(edges)} "
                    f"edges [{pruned_info}] "
                    f"(res_thresh={res_threshold:.1f}px, dy_median={med_dy:.1f}px)"
                )
                # Recursive call with clean edges (bounded recursion: edge count
                # decreases each iteration, at most log(N) levels).
                out = _bundle_adjust_affine(
                    clean_edges, num_frames, iterations, use_affine
                )

    return out


# ---------------------------------------------------------------------------
# §1.1D — Adaptive GNC f_scale (S30)
# ---------------------------------------------------------------------------


def _compute_adaptive_f_scale(
    edges: List[Dict],
    affines: List[np.ndarray],
    floor: float = 5.0,
) -> float:
    """Derive a data-driven Cauchy loss scale from post-solve edge residuals.

    Returns max(floor, 2.0 × median_residual_px).

    For clean datasets (median residual ≈ 2 px) the floor dominates and
    behaviour is unchanged from the fixed _BA_F_SCALE=10.  For uniformly
    noisy datasets (all edges have ~30 px residuals) the scale widens to
    ~60 px so the Cauchy loss does not over-penalise legitimate edges
    during the re-solve.

    Parameters
    ----------
    edges   : edge list (same format as _bundle_adjust_affine)
    affines : current best affine estimate, one per frame
    floor   : minimum returned scale (should be >= _BA_F_SCALE)
    """
    if not edges:
        return floor
    res_mags: List[float] = []
    for e in edges:
        ei, ej = e["i"], e["j"]
        if ei >= len(affines) or ej >= len(affines):
            continue
        pred_dx = float(affines[ej][0, 2]) - float(affines[ei][0, 2])
        pred_dy = float(affines[ej][1, 2]) - float(affines[ei][1, 2])
        obs_dx = -float(e["M"][0, 2])
        obs_dy = -float(e["M"][1, 2])
        res_mags.append(
            float(np.sqrt((pred_dx - obs_dx) ** 2 + (pred_dy - obs_dy) ** 2))
        )
    if not res_mags:
        return floor
    return float(max(floor, 2.0 * float(np.median(res_mags))))


__all__ = [
    "_bundle_adjust_affine",
    "_compute_adaptive_f_scale",
    "_spanning_tree_inlier_filter",
]
