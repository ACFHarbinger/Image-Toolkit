"""As-Rigid-As-Possible (ARAP) mesh puppeteering (roadmap §3.3, issue #194).

The highest-effort item in the cel_shaded_generator colorization/animation roadmap:
deterministic, mesh-based deformation of a static panel -- the counterpart
to Live2D-style puppeteering. An artist drags a small subset of "anchor"
vertices to new positions; the rest of the mesh follows in a way that
locally preserves rigidity (no shear/stretch) as much as possible, per
Sorkine & Alexa's As-Rigid-As-Possible surface modeling energy, adapted here
to a 2D triangle mesh with per-triangle (not per-vertex) rotations, matching
issue #194's own stated formulation ("per-triangle optimal rotation via
SVD").

**Algorithm**, alternating two steps until convergence:

1. *Local step*: for each triangle, given the current vertex position
   estimate, find the rigid rotation ``R_t`` (2x2 orthogonal, det=+1) that
   best explains how that triangle's edges have moved from their rest
   lengths/directions -- the classic 2D orthogonal Procrustes problem,
   solved via SVD.
2. *Global step*: with every triangle's ``R_t`` fixed, solve for new vertex
   positions minimizing ``sum_t sum_{edges in t} |(q_j-q_i) - R_t(p_j-p_i)|^2``
   -- a sparse linear least-squares problem whose normal equations are
   exactly a graph Laplacian over the mesh's edges (each triangle occurrence
   of an edge contributes weight 1), solved once per iteration via
   `scipy.sparse.linalg.splu` with anchor vertices pinned via the same
   Dirichlet row-replacement trick `colorization.py`'s `_solve_chrominance`
   already uses for scribbled pixels. The Laplacian itself doesn't depend on
   the rotations (only on mesh topology and rest positions), so it's
   factorized once and reused across iterations.

**Scope of this module vs. issue #194's full scope, documented
transparently:** this ships `arap_deform()` (the core solver) and
`generate_mesh()` (grid-sampling + Delaunay triangulation over a caller-
supplied binary mask, filtered to the mask's interior). It does **not**
ship a rigging UI (drag control vertices) or real-time re-solve GUI wiring
-- issue #194 explicitly lists those as part of its ~2+ week scope, and this
module is the deterministic algorithmic core they'd sit on top of, following
this session's established pattern of shipping backend mechanisms ahead of
GUI wiring (see issue #191's own two-part delivery). It also does **not**
depend on automatic character isolation (issue #184, line art extraction --
itself unbuilt, needing external PiDiNet/model integration): `generate_mesh()`
takes any caller-supplied binary mask, matching the roadmap's own established
"manual-mask MVP first" pattern used elsewhere (§1.1). Pure Python/NumPy/
SciPy, not the roadmap's originally-proposed C++ `base::cel_shaded_generator::arap_deform()`
Eigen kernel -- the same deliberate, documented deviation this session's
other solvers (`colorization.py`, `temporal.py`, etc.) already made, for the
same reason: avoids a new build-system surface before the algorithm itself
is proven correct; SciPy's sparse LU solver and NumPy's SVD are fast enough
for interactive-scale meshes (hundreds of vertices).
"""

from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.spatial import Delaunay

from ..runtime import NATIVE_COMPUTE_LOCK

__all__ = ["generate_mesh", "arap_deform"]

# Local (within-triangle) vertex index pairs forming each of a triangle's 3
# undirected edges. Order doesn't encode a traversal direction -- the ARAP
# energy term |(q_j-q_i) - R(p_j-p_i)|^2 is direction-symmetric (negating
# both sides of the difference leaves the squared norm unchanged), so which
# endpoint is treated as "i" vs. "j" doesn't affect the result.
_EDGE_PAIRS = ((0, 1), (1, 2), (2, 0))


def generate_mesh(mask: np.ndarray, grid_step: int = 16) -> tuple[np.ndarray, np.ndarray]:
    """Generate a 2D triangle mesh covering ``mask``'s True region.

    Samples a regular grid of points at ``grid_step`` spacing, keeps only
    the points that fall inside the mask, Delaunay-triangulates them, and
    discards any triangle whose centroid lands outside the mask (so the
    mesh doesn't bridge across concave gaps/holes via the triangulation's
    convex-hull tendency). Vertices left unreferenced by any surviving
    triangle are dropped and the remaining ones re-indexed contiguously --
    an unreferenced vertex would otherwise leave a structurally zero row in
    :func:`arap_deform`'s Laplacian, which `splu` can't factor.

    Args:
        mask: HxW boolean (or truthy) array marking the region to mesh.
        grid_step: spacing in pixels between candidate mesh vertices --
            smaller values give a finer mesh (more local rigidity fidelity,
            more triangles to solve for) at the cost of solve time.

    Returns:
        ``(vertices, triangles)`` where ``vertices`` is ``(N, 2)`` float64
        ``(x, y)`` pixel coordinates and ``triangles`` is ``(M, 3)`` int64
        vertex-index triples.
    """
    h, w = mask.shape
    ys = np.arange(0, h, grid_step)
    xs = np.arange(0, w, grid_step)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    grid_y = grid_y.ravel()
    grid_x = grid_x.ravel()

    inside = mask[grid_y, grid_x].astype(bool)
    pts_y = grid_y[inside]
    pts_x = grid_x[inside]
    if pts_y.size < 3:
        raise ValueError(
            f"mask covers too few grid points ({pts_y.size}) to build a mesh "
            f"at grid_step={grid_step} "
            "-- reduce grid_step or check the mask"
        )

    vertices = np.stack([pts_x, pts_y], axis=1).astype(np.float64)

    # Same MANGA_COLORIZE_LOCK serialization as arap_deform() (see that
    # function's own comment) -- Delaunay triangulation is also a compiled
    # native call (Qhull), so it's guarded by the same established
    # SIGSEGV-crash-class mitigation.
    with NATIVE_COMPUTE_LOCK:
        triangulation = Delaunay(vertices)
    triangles = triangulation.simplices

    centroids = vertices[triangles].mean(axis=1)
    cx = np.clip(centroids[:, 0].astype(np.int64), 0, w - 1)
    cy = np.clip(centroids[:, 1].astype(np.int64), 0, h - 1)
    keep = mask[cy, cx].astype(bool)
    triangles = triangles[keep]

    if triangles.size == 0:
        raise ValueError(
            "no triangle centroid fell inside the mask -- the sampled points likely straddle a "
            "concave/disconnected region; try a smaller grid_step"
        )

    used = np.unique(triangles)
    remap = np.full(vertices.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(used.size)
    vertices = vertices[used]
    triangles = remap[triangles]

    return vertices, triangles


def _build_arap_laplacian(triangles: np.ndarray, n: int) -> sparse.csr_matrix:
    """The (rotation-independent) combinatorial graph Laplacian over the
    mesh's edges -- see the module docstring's global-step derivation.
    Each triangle occurrence of an edge (i, j) contributes 1 to L[i,i],
    L[j,j] and -1 to L[i,j], L[j,i]."""
    rows = []
    cols = []
    data = []
    diag = np.zeros(n, dtype=np.float64)

    for va, vb, vc in triangles:
        verts = (va, vb, vc)
        for li, lj in _EDGE_PAIRS:
            i, j = verts[li], verts[lj]
            rows.extend((i, j))
            cols.extend((j, i))
            data.extend((-1.0, -1.0))
            diag[i] += 1.0
            diag[j] += 1.0

    rows.extend(range(n))
    cols.extend(range(n))
    data.extend(diag.tolist())

    return sparse.coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()


def _local_step(vertices: np.ndarray, q: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Per-triangle optimal rotation (2D orthogonal Procrustes via SVD)."""
    rotations = np.empty((triangles.shape[0], 2, 2), dtype=np.float64)

    for t_idx, (va, vb, vc) in enumerate(triangles):
        verts = (va, vb, vc)
        s = np.zeros((2, 2), dtype=np.float64)
        for li, lj in _EDGE_PAIRS:
            i, j = verts[li], verts[lj]
            e_rest = vertices[i] - vertices[j]
            e_def = q[i] - q[j]
            s += np.outer(e_rest, e_def)

        u, _, vt = np.linalg.svd(s)
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            # Reflection, not a rotation -- flip the singular vector paired
            # with the smallest singular value and recompute (standard
            # Procrustes reflection-correction).
            u = u.copy()
            u[:, -1] *= -1
            r = vt.T @ u.T
        rotations[t_idx] = r

    return rotations


def _global_step_rhs(
    vertices: np.ndarray, triangles: np.ndarray, rotations: np.ndarray, n: int
) -> np.ndarray:
    b = np.zeros((n, 2), dtype=np.float64)
    for t_idx, (va, vb, vc) in enumerate(triangles):
        verts = (va, vb, vc)
        r = rotations[t_idx]
        for li, lj in _EDGE_PAIRS:
            i, j = verts[li], verts[lj]
            contrib = r @ (vertices[i] - vertices[j])
            b[i] += contrib
            b[j] -= contrib
    return b


def arap_deform(
    vertices: np.ndarray,
    triangles: np.ndarray,
    anchors: dict[int, tuple[float, float]],
    n_iters: int = 10,
) -> np.ndarray:
    """As-Rigid-As-Possible deformation: move ``anchors`` to their target
    positions, solve for every other vertex's new position to locally
    preserve the mesh's rest-pose rigidity as much as possible.

    Args:
        vertices: ``(N, 2)`` rest-pose vertex positions (see
            :func:`generate_mesh`).
        triangles: ``(M, 3)`` vertex-index triples.
        anchors: ``{vertex_index: (x, y)}`` target positions for the
            vertices being dragged -- at least one is required. Every
            vertex not in this dict is free to move.
        n_iters: number of local/global alternations. ARAP typically
            converges visually within a handful of iterations; more
            iterations refine the rotation estimates further at linear
            extra cost (the Laplacian factorization is reused, so each
            extra iteration is one local-step SVD pass + two sparse solves).

    Returns:
        ``(N, 2)`` new vertex positions. Anchor rows are pinned exactly to
        their target; free vertices are the ARAP solve's result.
    """
    if not anchors:
        raise ValueError("arap_deform requires at least one anchor vertex")

    vertices = np.asarray(vertices, dtype=np.float64)
    n = vertices.shape[0]

    anchor_idx = np.array(sorted(anchors.keys()), dtype=np.int64)
    if anchor_idx.min() < 0 or anchor_idx.max() >= n:
        raise ValueError(f"anchor vertex index out of range for a {n}-vertex mesh")

    # Serializes the SciPy/NumPy-heavy solve (SVD per local step, sparse LU
    # factorization) across concurrent calls -- see
    # telemetry.MANGA_COLORIZE_LOCK's docstring for why every other cel_shaded_generator
    # solver in this codebase does the same (a documented SIGSEGV crash
    # class when PySide6/Shiboken's introspection hooks are loaded
    # in-process alongside certain native BLAS/LAPACK calls). Validation
    # above stays outside the lock since it's cheap and independent of any
    # shared/native state.
    with NATIVE_COMPUTE_LOCK:
        return _arap_deform_impl(vertices, triangles, anchor_idx, anchors, n, n_iters)


def _arap_deform_impl(
    vertices: np.ndarray,
    triangles: np.ndarray,
    anchor_idx: np.ndarray,
    anchors: dict[int, tuple[float, float]],
    n: int,
    n_iters: int,
) -> np.ndarray:
    anchor_targets = np.array([anchors[int(i)] for i in anchor_idx], dtype=np.float64)

    q = vertices.copy()
    q[anchor_idx] = anchor_targets

    laplacian = _build_arap_laplacian(triangles, n).tolil()
    for idx in anchor_idx:
        laplacian.rows[idx] = [idx]
        laplacian.data[idx] = [1.0]
    lu = splu(laplacian.tocsc())

    for _ in range(n_iters):
        rotations = _local_step(vertices, q, triangles)
        b = _global_step_rhs(vertices, triangles, rotations, n)
        b[anchor_idx] = anchor_targets
        q = np.column_stack([lu.solve(b[:, 0]), lu.solve(b[:, 1])])

    return q
