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

    # Initial sequential guess
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
        reg_identity = 1000.0
        if use_affine:
            for f in range(1, num_frames):
                res.append((x[f * 4] - 1.0) * reg_identity)  # a
                res.append(x[f * 4 + 1] * reg_identity)  # b

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

    out: List[np.ndarray] = []
    for f in range(num_frames):
        if use_affine:
            a, b, tx, ty = x_opt[f * 4 : f * 4 + 4]
            M = np.array([[a, b, tx], [-b, a, ty]], dtype=np.float32)
        else:
            M = np.eye(2, 3, dtype=np.float32)
            M[0, 2] = float(x_opt[f * 2])
            M[1, 2] = float(x_opt[f * 2 + 1])
        out.append(M)
    return out


__all__ = ["_bundle_adjust_affine"]
