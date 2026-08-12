"""Exact numerical solver jobs mirroring ``logic/include/exact_solvers.hpp``.

`call_hie_exact_solver` dispatches by `method` name to a pure-Python
reference implementation of the same algorithm the C++ header documents
(`solve_seam`, `solve_color_harmonization`) — this is the stub AGENT_BUS.md's
"Gemini -> Chat" note asked for, upgraded from a bare placeholder to a real
(if unoptimized) implementation so callers get correct results today.
`solve_seam`'s native binding is available (opt-in) via
`logic_bridge.native_solve_seam`, but not wired into this dispatch — its
tests depend on the reference's per-row progress reporting, which a single
blocking native call can't provide.

`solve_color_harmonization` takes an `enforce_bounds` flag (default
`False`, preserving the original exact-moment-matching contract). When
`True`, the result's `beta` is clamped into the valid Lab range (a
non-clipping guarantee) — via `logic_bridge.native_solve_color_harmonization`
when `base.hie` is available, or `_clamp_beta` (a pure-Python mirror of the
same, sequencing-bug-fixed C++ logic, see `cb118ac`) otherwise, so behavior
is identical either way. This has no progress-reporting concern (color
harmonization was never incremental), which is why — unlike seam/PSO/DE —
it's fine to route straight to native by default when requested. See
`.agent/cache/claude/hie_exact_solver_clamp_bug_20260812.md` for why exact
moments and bounds-clamping can't both hold for every input (the product
decision behind this flag).

GNC-TLS layer alignment (`solve_alignment_gnc`) has no pure-Python reference
here — it depends on a real feature-correspondence pipeline (see
`hie_claude_handoff_20260812.md`'s GNC-TLS centering fix) that doesn't have a
meaningful pure-Python fallback worth maintaining in parallel with the C++
implementation. `call_hie_alignment_gnc` below routes straight through
`logic_bridge.native_solve_alignment_gnc` and raises if the native binding
isn't available — there's no reference to fall back to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..logic_bridge.solvers import (
    HAVE_NATIVE_HIE,
    native_solve_alignment_gnc,
    native_solve_color_harmonization,
)
from .base import CancelToken, JobHandle, JobProgress, ReportFn, submit_job

Method = Literal["seam", "color_harmonization"]


@dataclass(frozen=True)
class SeamPixel:
    energy: float
    masked: bool = False


@dataclass(frozen=True)
class SeamResult:
    seam_x: list[int]
    total_energy: float
    success: bool
    error: str = ""


@dataclass(frozen=True)
class LayerColorStats:
    mean_l: float
    mean_a: float
    mean_b: float
    std_l: float
    std_a: float
    std_b: float


@dataclass(frozen=True)
class ColorHarmonizationResult:
    alpha_l: float
    beta_l: float
    alpha_a: float
    beta_a: float
    alpha_b: float
    beta_b: float
    success: bool
    error: str = ""


@dataclass(frozen=True)
class Correspondence:
    src_x: float
    src_y: float
    dst_x: float
    dst_y: float


@dataclass(frozen=True)
class MotionModel2DTS:
    tx: float = 0.0
    ty: float = 0.0
    scale: float = 1.0


@dataclass(frozen=True)
class AlignmentResult:
    model: MotionModel2DTS
    residual: float
    inlier_count: int
    success: bool
    error: str = ""


_MASKED_COST = float("inf")


def _solve_seam(
    energy_grid: list[list[SeamPixel]], token: CancelToken, report: ReportFn
) -> SeamResult:
    """Minimum-energy vertical seam via row-by-row dynamic programming.

    `energy_grid` is row-major: `energy_grid[row][col]`. Masked pixels carry
    infinite cost, preventing the seam from crossing protected regions —
    matches `exact_solvers.hpp`'s documented behavior.
    """
    rows = len(energy_grid)
    if rows == 0 or len(energy_grid[0]) == 0:
        return SeamResult(seam_x=[], total_energy=0.0, success=False, error="empty energy grid")
    cols = len(energy_grid[0])

    # cost[r][c] = min cumulative energy of a seam ending at (r, c)
    cost = [[0.0] * cols for _ in range(rows)]
    backtrack = [[0] * cols for _ in range(rows)]
    for c in range(cols):
        px = energy_grid[0][c]
        cost[0][c] = _MASKED_COST if px.masked else px.energy

    for r in range(1, rows):
        token.raise_if_cancelled()
        for c in range(cols):
            px = energy_grid[r][c]
            if px.masked:
                cost[r][c] = _MASKED_COST
                continue
            lo, hi = max(0, c - 1), min(cols - 1, c + 1)
            best_prev = min(range(lo, hi + 1), key=lambda cc: cost[r - 1][cc])
            cost[r][c] = px.energy + cost[r - 1][best_prev]
            backtrack[r][c] = best_prev
        report(JobProgress(fraction=r / (rows - 1), message=f"row {r}/{rows - 1}"))

    last_row = cost[rows - 1]
    end_c = min(range(cols), key=lambda c: last_row[c])
    if last_row[end_c] == _MASKED_COST:
        return SeamResult(seam_x=[], total_energy=0.0, success=False, error="no unmasked path exists")

    seam_x = [0] * rows
    seam_x[rows - 1] = end_c
    c = end_c
    for r in range(rows - 1, 0, -1):
        c = backtrack[r][c]
        seam_x[r - 1] = c

    return SeamResult(seam_x=seam_x, total_energy=last_row[end_c], success=True)


def _clamp_beta(alpha: float, beta: float, lo_bound: float, hi_bound: float) -> float:
    """Pure-Python mirror of `exact_solvers.cpp`'s (sequencing-bug-fixed) `clamp_beta`.

    Projects `beta` so `alpha * in + beta` stays within `[lo_bound, hi_bound]`
    for `in` ranging over the same `[lo_bound, hi_bound]` interval (the only
    way the three call sites below ever use it — source and output range are
    always identical). `hi` is recomputed after the low-bound correction, not
    read from a stale pre-correction value — see `cb118ac`'s fix and
    `logic/test/test_solvers.cpp::test_color_harmonization_clamp_beta_sequencing`.
    For `alpha` far enough from 1 no single shift can satisfy both bounds at
    once; this clamps as close as a shift can get, biased toward the
    second-checked (high) bound, matching the native implementation exactly.
    """
    lo = alpha * lo_bound + beta
    if lo < lo_bound:
        beta += lo_bound - lo
    hi = alpha * hi_bound + beta
    if hi > hi_bound:
        beta -= hi - hi_bound
    return beta


def _solve_color_harmonization(
    source: LayerColorStats, target: LayerColorStats, *, enforce_bounds: bool = False
) -> ColorHarmonizationResult:
    """Closed-form per-channel affine color transfer (Reinhard-style mean/std matching).

    Solves ``out = alpha * in + beta`` per CIELab channel so that
    ``source``'s statistics map onto ``target``'s. This is the exact convex
    optimum for matching first and second moments — no iteration needed.

    `enforce_bounds=True` additionally clamps each channel's `beta` into the
    valid Lab range (non-clipping guarantee), trading exact moment-matching
    for bounded output when the two conflict — see module docstring.
    """

    def channel(std_src: float, std_dst: float, mean_src: float, mean_dst: float) -> tuple[float, float]:
        alpha = (std_dst / std_src) if std_src > 1e-8 else 1.0
        beta = mean_dst - alpha * mean_src
        return alpha, beta

    alpha_l, beta_l = channel(source.std_l, target.std_l, source.mean_l, target.mean_l)
    alpha_a, beta_a = channel(source.std_a, target.std_a, source.mean_a, target.mean_a)
    alpha_b, beta_b = channel(source.std_b, target.std_b, source.mean_b, target.mean_b)

    if enforce_bounds:
        beta_l = _clamp_beta(alpha_l, beta_l, 0.0, 100.0)
        beta_a = _clamp_beta(alpha_a, beta_a, -128.0, 127.0)
        beta_b = _clamp_beta(alpha_b, beta_b, -128.0, 127.0)

    return ColorHarmonizationResult(
        alpha_l=alpha_l, beta_l=beta_l,
        alpha_a=alpha_a, beta_a=beta_a,
        alpha_b=alpha_b, beta_b=beta_b,
        success=True,
    )


def call_hie_exact_solver(
    method: Method,
    *,
    energy_grid: list[list[SeamPixel]] | None = None,
    source: LayerColorStats | None = None,
    target: LayerColorStats | None = None,
    enforce_bounds: bool = False,
) -> JobHandle[SeamResult | ColorHarmonizationResult]:
    """Dispatch an exact-solver job by `method` name.

    - `method="seam"` requires `energy_grid`, returns a `SeamResult`.
    - `method="color_harmonization"` requires `source` and `target`, returns
      a `ColorHarmonizationResult`. `enforce_bounds=True` clamps `beta` into
      the valid Lab range (via native when available, a pure-Python mirror
      otherwise) instead of the default exact-moment-matching behavior —
      see module docstring for why this is opt-in.
    """
    if method == "seam":
        if energy_grid is None:
            raise ValueError("call_hie_exact_solver(method='seam') requires energy_grid")
        return submit_job(lambda token, report: _solve_seam(energy_grid, token, report))

    if method == "color_harmonization":
        if source is None or target is None:
            raise ValueError("call_hie_exact_solver(method='color_harmonization') requires source and target")
        if enforce_bounds and HAVE_NATIVE_HIE:
            return submit_job(lambda _token, _report: native_solve_color_harmonization(source, target))
        return submit_job(
            lambda _token, _report: _solve_color_harmonization(source, target, enforce_bounds=enforce_bounds)
        )

    raise ValueError(f"unknown exact-solver method: {method!r}")


def call_hie_alignment_gnc(
    correspondences: list[Correspondence],
    *,
    gnc_iterations: int = 8,
    inlier_threshold: float = 3.0,
) -> JobHandle[AlignmentResult]:
    """GNC-TLS robust 2D translation+scale alignment. Native-only — see module docstring.

    Raises `RuntimeError` synchronously (before any job is submitted) if the
    compiled `base.hie` extension isn't available, matching
    `logic_bridge.native_solve_alignment_gnc`'s own fail-fast behavior.
    """
    if not HAVE_NATIVE_HIE:
        raise RuntimeError(
            "call_hie_alignment_gnc requires the native base.hie extension "
            "(no pure-Python reference exists — see module docstring)"
        )

    def _body(_token: CancelToken, _report: ReportFn) -> AlignmentResult:
        native_result = native_solve_alignment_gnc(correspondences, gnc_iterations, inlier_threshold)
        model = MotionModel2DTS(
            tx=native_result.model.tx, ty=native_result.model.ty, scale=native_result.model.scale
        )
        return AlignmentResult(
            model=model,
            residual=native_result.residual,
            inlier_count=native_result.inlier_count,
            success=native_result.success,
            error=native_result.error,
        )

    return submit_job(_body)
