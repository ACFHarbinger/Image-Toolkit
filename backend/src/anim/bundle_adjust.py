"""
Global Levenberg-Marquardt bundle adjustment over an affine edge graph.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy.optimize import least_squares


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
            tx_acc = x[(f + 1) * stride + tx_slot] - 2 * x[f * stride + tx_slot] + x[(f - 1) * stride + tx_slot]
            ty_acc = x[(f + 1) * stride + ty_slot] - 2 * x[f * stride + ty_slot] + x[(f - 1) * stride + ty_slot]
            res.append(tx_acc * reg_traj)
            res.append(ty_acc * reg_traj)

        return np.array(res, np.float64)

    result = least_squares(
        residuals,
        x0,
        method="trf",
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
        _DY_RATIO_THRESH = 2.5
        _DY_ABS_THRESH = 100.0

        clean_mask: List[bool] = []
        for idx, e in enumerate(edges):
            # Check prong 1: point-wise residual
            if edge_residuals[idx] > res_threshold:
                clean_mask.append(False)
                continue
            # Check prong 2: edge displacement outlier
            dy_val = abs(float(e["M"][1, 2]))
            dy_ratio = dy_val / max(med_dy, 1.0)
            dy_dev = abs(dy_val - med_dy)
            if dy_ratio > _DY_RATIO_THRESH and dy_dev > _DY_ABS_THRESH:
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
                    f"{e['i']}→{e['j']}" for e, keep in zip(edges, clean_mask) if not keep
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


__all__ = ["_bundle_adjust_affine"]
