"""Exact numerical solver jobs mirroring ``logic/include/exact_solvers.hpp``.

`call_hie_exact_solver` dispatches by `method` name to a pure-Python
reference implementation of the same algorithm the C++ header documents
(`solve_seam`, `solve_color_harmonization`) — this is the stub AGENT_BUS.md's
"Gemini -> Chat" note asked for, upgraded from a bare placeholder to a real
(if unoptimized) implementation so callers get correct results today. Swap
the method bodies for calls into `middleware/src/hie_middleware/logic_bridge/`
once the pybind11 binding for `logic/src/exact_solvers.cpp` lands — the
`JobResult` shape and field names below are chosen to match
`SeamResult`/`ColorHarmonizationResult` in the C++ header so that swap is a
pure implementation change, not an API change.

GNC-TLS layer alignment (`solve_alignment_gnc`) is intentionally NOT stubbed
here: it depends on a real feature-correspondence pipeline (see
`hie_claude_handoff_20260812.md`'s GNC-TLS centering fix) that doesn't have a
meaningful pure-Python fallback worth maintaining in parallel with the C++
implementation. Route it through `logic_bridge` directly once bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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


def _solve_color_harmonization(
    source: LayerColorStats, target: LayerColorStats
) -> ColorHarmonizationResult:
    """Closed-form per-channel affine color transfer (Reinhard-style mean/std matching).

    Solves ``out = alpha * in + beta`` per CIELab channel so that
    ``source``'s statistics map onto ``target``'s. This is the exact convex
    optimum for matching first and second moments — no iteration needed.
    """

    def channel(std_src: float, std_dst: float, mean_src: float, mean_dst: float) -> tuple[float, float]:
        alpha = (std_dst / std_src) if std_src > 1e-8 else 1.0
        beta = mean_dst - alpha * mean_src
        return alpha, beta

    alpha_l, beta_l = channel(source.std_l, target.std_l, source.mean_l, target.mean_l)
    alpha_a, beta_a = channel(source.std_a, target.std_a, source.mean_a, target.mean_a)
    alpha_b, beta_b = channel(source.std_b, target.std_b, source.mean_b, target.mean_b)

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
) -> JobHandle[SeamResult | ColorHarmonizationResult]:
    """Dispatch an exact-solver job by `method` name.

    - `method="seam"` requires `energy_grid`, returns a `SeamResult`.
    - `method="color_harmonization"` requires `source` and `target`, returns
      a `ColorHarmonizationResult`.
    """
    if method == "seam":
        if energy_grid is None:
            raise ValueError("call_hie_exact_solver(method='seam') requires energy_grid")
        return submit_job(lambda token, report: _solve_seam(energy_grid, token, report))

    if method == "color_harmonization":
        if source is None or target is None:
            raise ValueError("call_hie_exact_solver(method='color_harmonization') requires source and target")
        return submit_job(lambda _token, _report: _solve_color_harmonization(source, target))

    raise ValueError(f"unknown exact-solver method: {method!r}")
